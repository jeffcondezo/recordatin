"""
Diagnóstico rápido de por qué enviar_alarmas_tomas no envía SMS.

Uso:
  python3 manage.py diagnosticar_sms_alarmas
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Paciente, TomaMedicamento
from paciente.constants import SMS_ANTICIPO_MAX_MINUTOS, SMS_REINTENTO_DESPUES_MINUTOS
from paciente.sms import labsmobile_configurado, normalizar_msisdn


class Command(BaseCommand):
    help = 'Explica por qué no se están enviando SMS de alarmas ahora.'

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        hoy = ahora.date()
        tz = timezone.get_current_timezone()
        inicio = ahora - timedelta(minutes=SMS_REINTENTO_DESPUES_MINUTOS)
        fin = ahora + timedelta(minutes=SMS_ANTICIPO_MAX_MINUTOS)

        self.stdout.write(f'Ahora (local): {ahora:%Y-%m-%d %H:%M:%S %Z}')
        self.stdout.write(f'Timezone: {tz}')
        self.stdout.write(
            f'Ventana SMS: {inicio:%H:%M} → {fin:%H:%M} '
            f'(-{SMS_ANTICIPO_MAX_MINUTOS}/+{SMS_REINTENTO_DESPUES_MINUTOS} min)',
        )
        self.stdout.write(f'LabsMobile configurado: {labsmobile_configurado()}')

        tomas = list(
            TomaMedicamento.objects.filter(fecha=hoy)
            .select_related('paciente', 'medicamento', 'medicamento__prescripcion')
            .order_by('hora_programada', 'pk')
        )
        self.stdout.write(f'Tomas de hoy: {len(tomas)}')

        if not tomas:
            self.stdout.write(self.style.WARNING(
                'No hay tomas para hoy. Ejecute: python3 manage.py generar_tomas_diarias',
            ))
            return

        en_ventana = 0
        for toma in tomas:
            programada = timezone.make_aware(
                datetime.combine(toma.fecha, toma.hora_programada),
                tz,
            )
            pac = toma.paciente
            motivos = []
            en_v = inicio <= programada <= fin
            if en_v:
                en_ventana += 1

            if toma.alarma_enviada_at:
                motivos.append(f'ya enviado {toma.alarma_enviada_at:%H:%M:%S}')
            if toma.estado not in (
                TomaMedicamento.ESTADO_PENDIENTE,
                TomaMedicamento.ESTADO_TARDIO,
            ):
                motivos.append(f'estado={toma.estado}')
            if not toma.medicamento.activo:
                motivos.append('med inactivo')
            if not toma.medicamento.prescripcion.activa:
                motivos.append('prescripción inactiva')
            if pac.grupo != Paciente.GRUPO_INTERVENCION:
                motivos.append(f'grupo={pac.grupo}')
            tel = (pac.telefono or '').strip()
            if not tel:
                motivos.append('sin teléfono')
            elif not normalizar_msisdn(tel):
                motivos.append(f'tel inválido ({tel})')
            if not en_v:
                if programada > fin:
                    motivos.append('aún falta para la ventana')
                else:
                    motivos.append('fuera de ventana (pasó el reintento)')

            marca = '>>' if en_v and not motivos else '  '
            self.stdout.write(
                f'{marca} {programada:%H:%M} {pac.codigo_estudio or pac.pk} '
                f'{pac.nombre_completo[:28]:<28} '
                f'{toma.medicamento.nombre[:16]:<16} '
                f'{" | ".join(motivos) or "OK PARA ENVIAR"}',
            )

        self.stdout.write('')
        self.stdout.write(f'Tomas dentro de la ventana horaria: {en_ventana}')
        ok = sum(
            1 for t in tomas
            if (inicio <= timezone.make_aware(
                datetime.combine(t.fecha, t.hora_programada), tz,
            ) <= fin)
            and t.alarma_enviada_at is None
            and t.estado in (
                TomaMedicamento.ESTADO_PENDIENTE,
                TomaMedicamento.ESTADO_TARDIO,
            )
            and t.medicamento.activo
            and t.medicamento.prescripcion.activa
            and t.paciente.grupo == Paciente.GRUPO_INTERVENCION
            and normalizar_msisdn((t.paciente.telefono or '').strip())
        )
        self.stdout.write(self.style.SUCCESS(f'Candidatas reales a SMS ahora: {ok}'))
        if ok == 0:
            self.stdout.write(self.style.WARNING(
                'Ninguna pasa todos los filtros. Revise las líneas con motivos arriba.',
            ))
