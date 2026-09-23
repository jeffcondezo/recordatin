"""Genera el PDF de consentimiento firmado (texto + firmas dinámicas)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from paciente.consentimiento_texto import (
    INVESTIGADORES,
    SECCIONES_CONSENTIMIENTO,
    TITULO_ESTUDIO,
)


def _ruta_firma_investigador(nombre_archivo: str) -> Path | None:
    """Busca la firma procesada (transparente) o el archivo original en la raíz."""
    if not nombre_archivo:
        return None
    img_dir = Path(settings.BASE_DIR) / 'paciente' / 'static' / 'paciente' / 'img'
    mapa = {
        'firma_i1.png': img_dir / 'firma_investigador_1.png',
        'firma_i2.png': img_dir / 'firma_investigador_2.png',
    }
    candidatos = []
    if nombre_archivo in mapa:
        candidatos.append(mapa[nombre_archivo])
    candidatos.extend([
        Path(settings.BASE_DIR) / nombre_archivo,
        img_dir / nombre_archivo,
        Path(getattr(settings, 'STATIC_ROOT', '') or '') / 'paciente' / 'img' / nombre_archivo,
    ])
    for ruta in candidatos:
        if ruta and ruta.is_file():
            return ruta
    return None


def _imagen_ajustada(ruta, max_width, max_height):
    """Image de ReportLab respetando proporción dentro de un rectángulo máximo."""
    from reportlab.lib.utils import ImageReader

    reader = ImageReader(str(ruta))
    iw, ih = reader.getSize()
    if not iw or not ih:
        return None
    scale = min(max_width / iw, max_height / ih)
    return Image(str(ruta), width=iw * scale, height=ih * scale)


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle(
            'CITitulo',
            parent=base['Heading1'],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=8,
            textColor=colors.HexColor('#0f172a'),
        ),
        'subtitulo': ParagraphStyle(
            'CISubtitulo',
            parent=base['Normal'],
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            spaceAfter=14,
            textColor=colors.HexColor('#334155'),
        ),
        'h2': ParagraphStyle(
            'CIH2',
            parent=base['Heading2'],
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor('#0f766e'),
        ),
        'p': ParagraphStyle(
            'CIP',
            parent=base['Normal'],
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        'li': ParagraphStyle(
            'CILI',
            parent=base['Normal'],
            fontSize=9.5,
            leading=12.5,
            alignment=TA_LEFT,
        ),
        'meta': ParagraphStyle(
            'CIMeta',
            parent=base['Normal'],
            fontSize=9,
            leading=12,
            spaceAfter=3,
        ),
        'firma_label': ParagraphStyle(
            'CIFirmaLabel',
            parent=base['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            spaceBefore=2,
        ),
        'small': ParagraphStyle(
            'CISmall',
            parent=base['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
        ),
    }


def generar_pdf_consentimiento_firmado(paciente) -> bytes:
    """
    Devuelve bytes de un PDF A4 con el texto del consentimiento,
    la firma del paciente (nombre + DNI) y el bloque de investigadores.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title='Consentimiento informado firmado',
        author='Recordatin',
    )
    estilos = _estilos()
    story = []

    story.append(Paragraph('CONSENTIMIENTO INFORMADO', estilos['titulo']))
    story.append(Paragraph(f'«{TITULO_ESTUDIO}»', estilos['subtitulo']))

    for bloque in SECCIONES_CONSENTIMIENTO:
        tipo = bloque['tipo']
        if tipo == 'h1':
            continue  # ya va en el encabezado
        if tipo == 'h2':
            story.append(Paragraph(bloque['texto'], estilos['h2']))
        elif tipo == 'p':
            story.append(Paragraph(bloque['texto'], estilos['p']))
        elif tipo == 'ul':
            items = [
                ListItem(Paragraph(item, estilos['li']), leftIndent=8, value='•')
                for item in bloque.get('items', [])
            ]
            story.append(
                ListFlowable(
                    items,
                    bulletType='bullet',
                    start='•',
                    leftIndent=12,
                    bulletFontSize=9,
                    spaceBefore=2,
                    spaceAfter=6,
                )
            )

    # Datos de aceptación
    fecha = paciente.consentimiento_aceptado_at or timezone.now()
    if timezone.is_aware(fecha):
        fecha_local = timezone.localtime(fecha)
    else:
        fecha_local = fecha

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f'<b>Fecha de aceptación:</b> {fecha_local.strftime("%d/%m/%Y %H:%M")}',
        estilos['meta'],
    ))
    if paciente.codigo_estudio:
        story.append(Paragraph(
            f'<b>Código de estudio:</b> {paciente.codigo_estudio}',
            estilos['meta'],
        ))

    # Firma del paciente
    story.append(Spacer(1, 12))
    story.append(Paragraph('FIRMA DEL PARTICIPANTE', estilos['h2']))

    firma_paciente_flow = []
    if paciente.consentimiento_firma:
        try:
            img = _imagen_ajustada(
                paciente.consentimiento_firma.path,
                max_width=6.5 * cm,
                max_height=2.6 * cm,
            )
            if img:
                img.hAlign = 'CENTER'
                firma_paciente_flow.append(img)
            else:
                raise ValueError('imagen vacía')
        except Exception:
            firma_paciente_flow.append(Paragraph(
                '<i>(Firma registrada; no se pudo incrustar la imagen)</i>',
                estilos['small'],
            ))
    else:
        firma_paciente_flow.append(Spacer(1, 2.2 * cm))

    firma_paciente_flow.append(Paragraph(
        f'<b>{paciente.nombre_completo}</b>',
        estilos['firma_label'],
    ))
    dni = (paciente.dni or '').strip() or '—'
    firma_paciente_flow.append(Paragraph(
        f'DNI: {dni}',
        estilos['firma_label'],
    ))
    firma_paciente_flow.append(Paragraph(
        'Participante / representante legal',
        estilos['small'],
    ))
    story.append(KeepTogether(firma_paciente_flow))

    # Firmas de investigadores
    story.append(Spacer(1, 14))
    story.append(Paragraph('FIRMAS DE LOS INVESTIGADORES', estilos['h2']))

    celdas = []
    for inv in INVESTIGADORES:
        partes = []
        ruta_firma = _ruta_firma_investigador(inv.get('firma') or '')
        if ruta_firma:
            try:
                img = _imagen_ajustada(ruta_firma, max_width=6.2 * cm, max_height=2.4 * cm)
                if img:
                    img.hAlign = 'CENTER'
                    partes.append(img)
            except Exception:
                partes.append(Paragraph('<br/><br/>', estilos['firma_label']))
                partes.append(Paragraph('_________________________', estilos['firma_label']))
        else:
            partes.append(Paragraph('<br/><br/>', estilos['firma_label']))
            partes.append(Paragraph('_________________________', estilos['firma_label']))

        partes.append(Paragraph(f'<b>{inv["nombre"]}</b>', estilos['firma_label']))
        dni_inv = (inv.get('dni') or '').strip()
        if dni_inv:
            partes.append(Paragraph(f'DNI: {dni_inv}', estilos['firma_label']))
        partes.append(Paragraph(inv['cargo'], estilos['small']))
        partes.append(Paragraph(inv['institucion'], estilos['small']))
        celdas.append(partes)

    while len(celdas) < 2:
        celdas.append([Paragraph('', estilos['small'])])

    tabla = Table([celdas[:2]], colWidths=[8.2 * cm, 8.2 * cm])
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(tabla)

    doc.build(story)
    return buffer.getvalue()
