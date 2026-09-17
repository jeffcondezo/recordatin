"""
Genera en el servidor las tomas del día para todos los pacientes de intervención.

No depende de que el paciente abra la app. Debe correr por cron, p. ej.:

  # Cada día a las 00:05 (y opcionalmente al arrancar el día)
  5 0 * * * cd /ruta/recordatin && python3 manage.py generar_tomas_diarias

  # Rellenar días faltantes (p. ej. una vez tras el deploy)
  python3 manage.py generar_tomas_diarias --dias 7

También se invoca al inicio de enviar_alarmas_tomas para asegurar el día de hoy.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from paciente.services import generar_tomas_para_todos


class Command(BaseCommand):
    help = (
        'Crea las tomas programadas en el backend para pacientes de intervención '
        '(hoy y, opcionalmente, días anteriores).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=1,
            help='Cuántos días generar hacia atrás incluyendo hoy (default: 1 = solo hoy).',
        )

    def handle(self, *args, **options):
        dias = max(1, int(options['dias']))
        hoy = timezone.localdate()
        total_pacientes = 0
        total_creadas = 0

        for offset in range(dias):
            fecha = hoy - timedelta(days=offset)
            n_pac, n_creadas = generar_tomas_para_todos(fecha=fecha)
            total_pacientes = max(total_pacientes, n_pac)
            total_creadas += n_creadas
            self.stdout.write(
                f'{fecha.isoformat()}: {n_pac} paciente(s), {n_creadas} toma(s) nueva(s)',
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Listo. Pacientes: {total_pacientes}; tomas nuevas: {total_creadas}',
            ),
        )
