from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import TomaMedicamento
from paciente.push import enviar_push_paciente


class Command(BaseCommand):
    help = 'Envía notificaciones push para tomas pendientes cuya hora programada es ahora.'

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        hoy = ahora.date()
        hora_actual = ahora.time().replace(second=0, microsecond=0)

        tomas = TomaMedicamento.objects.filter(
            fecha=hoy,
            estado=TomaMedicamento.ESTADO_PENDIENTE,
            hora_programada=hora_actual,
            alarma_enviada_at__isnull=True,
        ).select_related('medicamento', 'paciente')

        tomas = list(tomas)
        total = 0
        for toma in tomas:
            nombre = toma.medicamento.nombre
            dosis = toma.medicamento.dosis
            titulo = 'Recordatin — Es hora de su medicina'
            cuerpo = f'{nombre} ({dosis})'
            tag = f'toma-{toma.pk}'
            enviados = enviar_push_paciente(
                toma.paciente,
                titulo,
                cuerpo,
                tag=tag,
            )
            if enviados > 0:
                toma.alarma_enviada_at = timezone.now()
                toma.save(update_fields=['alarma_enviada_at'])
                total += enviados
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Alarma toma {toma.pk} → {enviados} dispositivo(s)',
                    ),
                )
            else:
                subs = toma.paciente.push_subscriptions.filter(
                    activo=True,
                    cuidador__isnull=True,
                ).count()
                if subs == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Toma {toma.pk}: sin suscripciones push activas',
                        ),
                    )

        self.stdout.write(f'Procesadas {len(tomas)} tomas a las {hora_actual:%H:%M}; pushes: {total}')
