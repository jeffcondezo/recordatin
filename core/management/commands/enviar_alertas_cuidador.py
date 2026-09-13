"""
Envía alertas push a cuidadores cuando el paciente no registra una toma
y recordatorios de citas médicas próximas.

Cron sugerido (junto a enviar_alarmas_tomas):
  */5 * * * * cd /ruta/recordatin && python manage.py enviar_alertas_cuidador
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import CitaMedica, Cuidador, TomaMedicamento
from paciente.constants import ALERTA_CUIDADOR_MINUTOS
from paciente.push import enviar_push_cuidadores


class Command(BaseCommand):
    help = 'Envía alertas a cuidadores por medicinas no registradas y citas próximas.'

    def handle(self, *args, **options):
        self._alertas_medicinas_olvidadas()
        self._recordatorios_citas()

    def _paciente_tiene_cuidadores(self, paciente):
        return Cuidador.objects.filter(paciente=paciente, activo=True).exists()

    def _alertas_medicinas_olvidadas(self):
        ahora = timezone.localtime()
        hoy = ahora.date()
        umbral = timedelta(minutes=ALERTA_CUIDADOR_MINUTOS)
        tz = timezone.get_current_timezone()

        tomas = TomaMedicamento.objects.filter(
            fecha=hoy,
            estado__in=(
                TomaMedicamento.ESTADO_PENDIENTE,
                TomaMedicamento.ESTADO_TARDIO,
            ),
            alerta_cuidador_enviada_at__isnull=True,
        ).select_related('medicamento', 'paciente')

        enviados = 0
        for toma in tomas:
            if not self._paciente_tiene_cuidadores(toma.paciente):
                continue

            programada = timezone.make_aware(
                datetime.combine(toma.fecha, toma.hora_programada),
                tz,
            )
            if ahora < programada + umbral:
                continue

            nombre_paciente = toma.paciente.nombre
            med = toma.medicamento.nombre
            hora = toma.hora_programada.strftime('%H:%M')
            titulo = 'Recordatin — Medicina sin registrar'
            cuerpo = (
                f'{nombre_paciente} no ha registrado {med} ({hora}). '
                'Puede llamarle para recordárselo.'
            )
            n = enviar_push_cuidadores(
                toma.paciente,
                titulo,
                cuerpo,
                url='/paciente/cuidador/',
                tag=f'olvido-{toma.pk}',
            )
            if n > 0:
                toma.alerta_cuidador_enviada_at = timezone.now()
                toma.save(update_fields=['alerta_cuidador_enviada_at'])
                enviados += n
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Alerta olvido toma {toma.pk} → {n} dispositivo(s)',
                    ),
                )

        self.stdout.write(f'Alertas de olvido enviadas: {enviados}')

    def _recordatorios_citas(self):
        ahora = timezone.now()
        ventana_inicio = ahora + timedelta(hours=23)
        ventana_fin = ahora + timedelta(hours=25)

        citas = CitaMedica.objects.filter(
            estado=CitaMedica.ESTADO_PROGRAMADA,
            fecha_hora__gte=ventana_inicio,
            fecha_hora__lte=ventana_fin,
            recordatorio_cuidador_enviado_at__isnull=True,
        ).select_related('paciente')

        enviados = 0
        for cita in citas:
            if not self._paciente_tiene_cuidadores(cita.paciente):
                continue

            local = timezone.localtime(cita.fecha_hora)
            titulo = 'Recordatin — Cita médica mañana'
            cuerpo = (
                f'{cita.paciente.nombre}: {cita.especialidad} '
                f'el {local:%d/%m/%Y} a las {local:%H:%M} en {cita.lugar}.'
            )
            n = enviar_push_cuidadores(
                cita.paciente,
                titulo,
                cuerpo,
                url='/paciente/cuidador/citas/',
                tag=f'cita-{cita.pk}',
            )
            if n > 0:
                cita.recordatorio_cuidador_enviado_at = timezone.now()
                cita.save(update_fields=['recordatorio_cuidador_enviado_at'])
                enviados += n
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Recordatorio cita {cita.pk} → {n} dispositivo(s)',
                    ),
                )

        self.stdout.write(f'Recordatorios de citas enviados: {enviados}')
