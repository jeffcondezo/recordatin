from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import TomaMedicamento
from paciente.constants import VENTANA_REINTENTO_ALARMA_MINUTOS
from paciente.push import enviar_push_paciente
from paciente.services import generar_tomas_para_todos


class Command(BaseCommand):
    help = (
        'Asegura tomas del día en el backend y envía notificaciones push '
        'para las pendientes en la ventana de reintento.'
    )

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        hoy = ahora.date()

        # Las tomas deben existir aunque el paciente no abra la app.
        n_pac, n_creadas = generar_tomas_para_todos(fecha=hoy)
        if n_creadas:
            self.stdout.write(
                f'Tomas generadas hoy: {n_creadas} ({n_pac} paciente(s))',
            )

        hasta = ahora.time().replace(second=0, microsecond=0)
        inicio_ventana = ahora - timedelta(minutes=VENTANA_REINTENTO_ALARMA_MINUTOS)

        filtro_hora = Q(hora_programada__lte=hasta)
        if inicio_ventana.date() == hoy:
            desde = inicio_ventana.time().replace(second=0, microsecond=0)
            filtro_hora &= Q(hora_programada__gte=desde)

        tomas = (
            TomaMedicamento.objects.filter(
                fecha=hoy,
                estado__in=(
                    TomaMedicamento.ESTADO_PENDIENTE,
                    TomaMedicamento.ESTADO_TARDIO,
                ),
                alarma_enviada_at__isnull=True,
                medicamento__activo=True,
                medicamento__prescripcion__activa=True,
            )
            .filter(filtro_hora)
            .select_related('medicamento', 'paciente')
        )

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
                toma_id=toma.pk,
            )
            if enviados > 0:
                toma.alarma_enviada_at = timezone.now()
                toma.save(update_fields=['alarma_enviada_at'])
                total += enviados
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Alarma toma {toma.pk} ({toma.hora_programada:%H:%M}) '
                        f'→ {enviados} dispositivo(s)',
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

        self.stdout.write(
            f'Ventana {VENTANA_REINTENTO_ALARMA_MINUTOS} min hasta {hasta:%H:%M}; '
            f'candidatas {len(tomas)}; pushes: {total}',
        )
