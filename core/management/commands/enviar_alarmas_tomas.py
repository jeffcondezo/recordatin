from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import TomaMedicamento
from paciente.constants import (
    SMS_ANTICIPO_MAX_MINUTOS,
    SMS_MAX_CARACTERES,
    VENTANA_REINTENTO_ALARMA_MINUTOS,
)
from paciente.push import enviar_push_paciente
from paciente.services import generar_tomas_para_todos
from paciente.sms import (
    enviar_sms_paciente,
    labsmobile_configurado,
    mensaje_recordatorio_grupo,
)


class Command(BaseCommand):
    help = (
        'Asegura tomas del día y envía recordatorios '
        '(SMS agrupados ~5–10 min antes, o push legacy).'
    )

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        hoy = ahora.date()
        canal = getattr(settings, 'NOTIFICACIONES_CANAL', 'sms')

        n_pac, n_creadas = generar_tomas_para_todos(fecha=hoy)
        if n_creadas:
            self.stdout.write(
                f'Tomas generadas hoy: {n_creadas} ({n_pac} paciente(s))',
            )

        if canal == 'sms':
            total = self._enviar_sms_agrupados(ahora, hoy)
            self.stdout.write(
                f'Canal=sms; anticipo 0–{SMS_ANTICIPO_MAX_MINUTOS} min; '
                f'grupos enviados: {total}',
            )
        else:
            total = self._enviar_push(ahora, hoy)
            self.stdout.write(
                f'Canal=push; ventana {VENTANA_REINTENTO_ALARMA_MINUTOS} min; '
                f'enviados: {total}',
            )

    def _tomas_pendientes_hoy(self, hoy):
        return list(
            TomaMedicamento.objects.filter(
                fecha=hoy,
                estado__in=(
                    TomaMedicamento.ESTADO_PENDIENTE,
                    TomaMedicamento.ESTADO_TARDIO,
                ),
                alarma_enviada_at__isnull=True,
                medicamento__activo=True,
                medicamento__prescripcion__activa=True,
            ).select_related('medicamento', 'paciente')
        )

    def _enviar_sms_agrupados(self, ahora, hoy):
        if not labsmobile_configurado():
            self.stdout.write(
                self.style.ERROR(
                    'Canal SMS activo pero LabsMobile no está configurado '
                    '(LABSMOBILE_USERNAME / LABSMOBILE_TOKEN).',
                ),
            )
            return 0

        tz = timezone.get_current_timezone()
        limite_lejos = ahora + timedelta(minutes=SMS_ANTICIPO_MAX_MINUTOS)

        # Enlace a la app para registrar (SITE_URL o spentor.app por defecto).
        incluir_enlace = True

        grupos = defaultdict(list)
        for toma in self._tomas_pendientes_hoy(hoy):
            programada = timezone.make_aware(
                datetime.combine(toma.fecha, toma.hora_programada),
                tz,
            )
            # Enviar desde 10 min antes hasta la hora programada (ideal 5–10 min antes).
            if ahora <= programada <= limite_lejos:
                grupos[(toma.paciente_id, toma.hora_programada)].append(toma)

        total = 0
        for (_paciente_id, hora), tomas in sorted(grupos.items(), key=lambda x: x[0][1]):
            paciente = tomas[0].paciente
            # Solo intervención; control / no_definido no reciben SMS.
            if paciente.grupo != paciente.GRUPO_INTERVENCION:
                continue
            mensaje = mensaje_recordatorio_grupo(tomas, incluir_enlace=incluir_enlace)
            resultado = enviar_sms_paciente(paciente, mensaje)
            if resultado.get('ok'):
                ahora_envio = timezone.now()
                for toma in tomas:
                    toma.alarma_enviada_at = ahora_envio
                    toma.save(update_fields=['alarma_enviada_at'])
                total += 1
                nombres = ', '.join(t.medicamento.nombre for t in tomas)
                chars = resultado.get('chars', len(mensaje))
                self.stdout.write(
                    self.style.SUCCESS(
                        f'SMS {hora:%H:%M} paciente {paciente.pk} '
                        f'({len(tomas)} meds: {nombres}) '
                        f'{chars}/{SMS_MAX_CARACTERES} chars → {resultado.get("msisdn")}',
                    ),
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'SMS {hora:%H:%M} paciente {paciente.pk}: '
                        f'{resultado.get("error")} tel={paciente.telefono!r}',
                    ),
                )
        return total

    def _enviar_push(self, ahora, hoy):
        hasta = ahora.time().replace(second=0, microsecond=0)
        inicio_ventana = ahora - timedelta(minutes=VENTANA_REINTENTO_ALARMA_MINUTOS)
        total = 0
        for toma in self._tomas_pendientes_hoy(hoy):
            if toma.hora_programada > hasta:
                continue
            if inicio_ventana.date() == hoy:
                desde = inicio_ventana.time().replace(second=0, microsecond=0)
                if toma.hora_programada < desde:
                    continue
            enviados = enviar_push_paciente(
                toma.paciente,
                'Recordatin — Es hora de su medicina',
                f'{toma.medicamento.nombre} ({toma.medicamento.dosis})',
                tag=f'toma-{toma.pk}',
                toma_id=toma.pk,
            )
            if enviados > 0:
                toma.alarma_enviada_at = timezone.now()
                toma.save(update_fields=['alarma_enviada_at'])
                total += enviados
        return total
