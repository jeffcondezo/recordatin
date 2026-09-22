"""
Importa pacientes desde carga.xlsx (hoja «Datos generales») a partir del N.º 4 → P004.

Uso:
  python manage.py importar_carga_xlsx
  python manage.py importar_carga_xlsx --archivo carga.xlsx --desde 4 --dry-run
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.mmas8 import puntuar_respuestas
from core.models import EvaluacionMMAS8, MedicamentoPrescrito, Paciente
from maestro.forms import obtener_o_crear_prescripcion_activa

User = get_user_model()

# Índices de columna (fila de datos, 0-based sobre values_only)
COL_NOMBRE = 0
COL_NUM = 1
COL_DNI = 3
COL_CELULAR = 4
COL_EDAD = 5
COL_SEXO = 6
COL_ENF1 = 7
COL_ENF2 = 8
COL_ENF3 = 9
COL_MEDS = (10, 11, 12, 13)
COL_PREG = (14, 15, 16, 17, 18, 19, 20, 21)  # puntos MMAS ya puntuados


def _texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    return str(valor).strip()


def _codigo_desde_num(num: int) -> str:
    return f'P{num:03d}'


def _sexo(valor) -> str:
    v = _texto(valor).upper()
    if v in ('M', 'MASCULINO', 'H', 'HOMBRE'):
        return Paciente.SEXO_M
    if v in ('F', 'FEMENINO', 'MUJER'):
        return Paciente.SEXO_F
    return Paciente.SEXO_O


def _telefono(valor) -> str:
    """Solo dígitos locales de Perú (9). El envío SMS antepone 51."""
    digitos = ''.join(c for c in _texto(valor) if c.isdigit())
    if not digitos:
        return ''
    if digitos.startswith('51') and len(digitos) == 11:
        digitos = digitos[2:]
    if digitos.startswith('0') and len(digitos) == 10:
        digitos = digitos[1:]
    return digitos


def _punto(valor) -> Decimal | None:
    if valor is None or valor == '':
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def respuestas_desde_puntos(puntos):
    """
    El Excel trae el aporte al puntaje MMAS-8 (no sí/no crudo).
    Ítems 1–7: 1 = respuesta adherente, 0 = no adherente.
    Ítem 8: 0 / 0.25 / 0.50 / 0.75 / 1.00 = (1 − LikertScore).
    """
    if len(puntos) != 8 or any(p is None for p in puntos):
        return None

    resp = {}
    for i, clave in enumerate(('q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7'), start=0):
        p = puntos[i]
        adherente = p >= Decimal('0.5')
        if clave == 'q5':
            # ¿Tomó ayer? Sí = adherente
            resp[clave] = 'si' if adherente else 'no'
        else:
            # Sí = no adherente
            resp[clave] = 'no' if adherente else 'si'

    contrib = puntos[7]
    # contrib = 1 - LIKERT8_SCORES[likert]
    mapa = {
        Decimal('1.00'): 0,
        Decimal('0.75'): 1,
        Decimal('0.50'): 2,
        Decimal('0.25'): 3,
        Decimal('0.00'): 4,
    }
    likert = mapa.get(contrib.quantize(Decimal('0.01')))
    if likert is None:
        # Redondeo al más cercano
        opciones = [
            (abs(contrib - Decimal(k)), v)
            for k, v in (
                ('1', 0), ('0.75', 1), ('0.5', 2), ('0.25', 3), ('0', 4),
            )
        ]
        opciones.sort()
        likert = opciones[0][1]
    resp['q8'] = likert
    return resp


class Command(BaseCommand):
    help = 'Importa pacientes desde carga.xlsx a partir de P004 (slots libres).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo',
            default='carga.xlsx',
            help='Ruta al Excel (por defecto carga.xlsx en la raíz del proyecto).',
        )
        parser.add_argument(
            '--desde',
            type=int,
            default=4,
            help='Número de fila/participante mínimo (default 4 → P004).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué se importaría, sin escribir.',
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError(
                'Falta openpyxl. Instale con: pip install openpyxl',
            ) from exc

        ruta = Path(options['archivo'])
        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta
        if not ruta.exists():
            raise CommandError(f'No se encontró el archivo: {ruta}')

        desde = options['desde']
        dry = options['dry_run']

        wb = openpyxl.load_workbook(ruta, data_only=True)
        ws = wb.active
        filas = list(ws.iter_rows(min_row=6, values_only=True))

        candidatos = []
        for row in filas:
            num = row[COL_NUM]
            if num is None:
                continue
            try:
                num = int(num)
            except (TypeError, ValueError):
                continue
            if num < desde:
                continue
            nombre = _texto(row[COL_NOMBRE])
            if not nombre:
                continue
            candidatos.append((num, row))

        self.stdout.write(
            f'Archivo: {ruta.name} · desde N.º {desde} · '
            f'{len(candidatos)} filas con nombre',
        )

        actualizados = 0
        creados = 0
        mmas_ok = 0
        meds_ok = 0
        omitidos = 0

        for num, row in candidatos:
            codigo = _codigo_desde_num(num)
            nombre = _texto(row[COL_NOMBRE])
            dni = _texto(row[COL_DNI])
            telefono = _telefono(row[COL_CELULAR])
            try:
                edad = int(row[COL_EDAD]) if row[COL_EDAD] is not None else None
            except (TypeError, ValueError):
                edad = None
            sexo = _sexo(row[COL_SEXO])
            enf1 = _texto(row[COL_ENF1])
            enf2 = _texto(row[COL_ENF2])
            enf3 = _texto(row[COL_ENF3])
            meds = [_texto(row[i]) for i in COL_MEDS]
            meds = [m for m in meds if m]
            puntos = [_punto(row[i]) for i in COL_PREG]

            paciente = Paciente.objects.filter(codigo_estudio=codigo).first()
            if paciente is None:
                # Slot libre: crear usuario estudio.pNNN si no existe
                username = f'estudio.{codigo.lower()}'
                if dry:
                    self.stdout.write(
                        f'[dry-run] CREAR {codigo} = {nombre} '
                        f'(grupo=no_definido, meds={len(meds)})',
                    )
                    creados += 1
                    continue
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={'email': f'{username}@recordatin.local'},
                )
                if not user.has_usable_password():
                    user.set_password(codigo.lower())
                    user.save()
                paciente = Paciente(user=user, codigo_estudio=codigo)
                es_nuevo = True
            else:
                # Solo sobrescribir placeholders «Participante …» o mismos códigos
                es_placeholder = (paciente.nombre or '').startswith('Participante')
                if not es_placeholder and paciente.nombre_completo.upper() != nombre.upper():
                    # Ya tiene datos reales distintos: actualizar igual (pedido: P004+)
                    pass
                es_nuevo = False
                if dry:
                    self.stdout.write(
                        f'[dry-run] ACTUALIZAR {codigo} = {nombre} '
                        f'(grupo=no_definido, meds={len(meds)})',
                    )
                    actualizados += 1
                    continue

            if dry:
                omitidos += 1
                continue

            with transaction.atomic():
                paciente.nombre = nombre
                paciente.apellidos = ''
                paciente.dni = dni
                paciente.telefono = telefono
                paciente.edad = edad
                paciente.fecha_nacimiento = None
                paciente.sexo = sexo
                paciente.diagnostico_principal = enf1
                paciente.enfermedad_2 = enf2
                paciente.enfermedad_3 = enf3
                paciente.grupo = Paciente.GRUPO_NO_DEFINIDO
                paciente.activo = True
                if not paciente.fecha_ingreso_estudio:
                    paciente.fecha_ingreso_estudio = timezone.localdate()
                paciente.save()

                if es_nuevo:
                    creados += 1
                else:
                    actualizados += 1

                # Medicamentos (sin horarios → no generan SMS hasta configurar)
                if meds:
                    n_meds = self._sincronizar_medicamentos(paciente, meds)
                    meds_ok += n_meds

                # MMAS-8 basal desde puntajes del Excel
                resp = respuestas_desde_puntos(puntos)
                if resp:
                    puntaje, categoria = puntuar_respuestas(resp)
                    existente = EvaluacionMMAS8.objects.filter(
                        paciente=paciente,
                        momento=EvaluacionMMAS8.MOMENTO_BASAL,
                    ).first()
                    if existente:
                        existente.respuestas = resp
                        existente.puntaje = puntaje
                        existente.categoria = categoria
                        existente.registrado_por = EvaluacionMMAS8.ORIGEN_ADMIN
                        existente.fecha = timezone.now()
                        existente.save(
                            update_fields=[
                                'respuestas', 'puntaje', 'categoria',
                                'registrado_por', 'fecha',
                            ],
                        )
                    else:
                        EvaluacionMMAS8.objects.create(
                            paciente=paciente,
                            momento=EvaluacionMMAS8.MOMENTO_BASAL,
                            respuestas=resp,
                            puntaje=puntaje,
                            categoria=categoria,
                            registrado_por=EvaluacionMMAS8.ORIGEN_ADMIN,
                        )
                    mmas_ok += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'{codigo} = {nombre} | edad={edad} | tel={telefono or "-"} '
                    f'| meds={len(meds)} | grupo=no_definido',
                ),
            )

        self.stdout.write('')
        self.stdout.write(
            f'Listo. creados={creados} actualizados={actualizados} '
            f'mmas_basal={mmas_ok} medicamentos_tocados={meds_ok}'
            + (' (dry-run)' if dry else ''),
        )

    def _sincronizar_medicamentos(self, paciente, nombres_meds):
        """Crea/actualiza medicamentos activos por nombre; sin horarios."""
        presc = obtener_o_crear_prescripcion_activa(paciente)
        # Desactivar los que ya no están en la lista (solo los sin horario
        # importados), manteniendo los que el investigador haya editado con horas.
        existentes = {
            m.nombre.strip().upper(): m
            for m in MedicamentoPrescrito.objects.filter(
                prescripcion=presc,
                activo=True,
            )
        }
        tocados = 0
        vistos = set()
        for nombre in nombres_meds:
            key = nombre.upper()
            vistos.add(key)
            med = existentes.get(key)
            if med:
                continue
            MedicamentoPrescrito.objects.create(
                prescripcion=presc,
                nombre=nombre,
                dosis='',
                via=MedicamentoPrescrito.VIA_ORAL,
                instrucciones='Importado desde carga.xlsx (sin horario aún).',
                activo=True,
            )
            tocados += 1
        return tocados
