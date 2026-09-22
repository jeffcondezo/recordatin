"""
Envía un SMS de prueba por LabsMobile.

  python manage.py probar_sms --telefono 51999999999
  python manage.py probar_sms --paciente-id 1
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import Paciente
from paciente.sms import enviar_sms, enviar_sms_paciente, labsmobile_configurado


class Command(BaseCommand):
    help = 'Envía un SMS de prueba vía LabsMobile.'

    def add_arguments(self, parser):
        parser.add_argument('--telefono', type=str, default='', help='MSISDN o número local')
        parser.add_argument('--paciente-id', type=int, default=0)
        parser.add_argument(
            '--mensaje',
            type=str,
            default='Recordatin: SMS de prueba. Si lo recibe, LabsMobile está bien configurado.',
        )

    def handle(self, *args, **options):
        if not labsmobile_configurado():
            raise CommandError(
                'Configure LABSMOBILE_USERNAME y LABSMOBILE_TOKEN en el entorno.',
            )

        telefono = (options['telefono'] or '').strip()
        paciente_id = options['paciente_id']
        mensaje = options['mensaje']

        if paciente_id:
            paciente = Paciente.objects.filter(pk=paciente_id).first()
            if not paciente:
                raise CommandError(f'Paciente {paciente_id} no encontrado')
            resultado = enviar_sms_paciente(paciente, mensaje)
        elif telefono:
            resultado = enviar_sms(telefono, mensaje)
        else:
            raise CommandError('Indique --telefono o --paciente-id')

        if resultado.get('ok'):
            self.stdout.write(
                self.style.SUCCESS(f'OK → {resultado.get("msisdn")} raw={resultado.get("raw")}'),
            )
        else:
            raise CommandError(
                f'Falló: {resultado.get("error")} raw={resultado.get("raw")}',
            )
