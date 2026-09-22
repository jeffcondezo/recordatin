from datetime import date, timedelta
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Paciente

User = get_user_model()

DIAGNOSTICOS = [
    'Hipertensión arterial',
    'Diabetes mellitus tipo 2',
    'Dislipidemia',
    'Hipertensión arterial y diabetes mellitus tipo 2',
    'Insuficiencia cardiaca crónica',
    'Asma bronquial',
    'EPOC',
]


class Command(BaseCommand):
    help = (
        'Crea el administrador del estudio y ~300 pacientes '
        '(intervención / control balanceados).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--total',
            type=int,
            default=300,
            help='Número de pacientes de estudio a crear (default 300).',
        )
        parser.add_argument(
            '--password-admin',
            default='estudio2026',
            help='Contraseña del usuario admin.estudio',
        )
        parser.add_argument(
            '--password-pacientes',
            default='paciente123',
            help='Contraseña común de los pacientes de estudio',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        total = options['total']
        pwd_admin = options['password_admin']
        pwd_pac = options['password_pacientes']

        admin_user, created = User.objects.get_or_create(
            username='admin.estudio',
            defaults={
                'email': 'admin.estudio@recordatin.local',
                'is_staff': True,
                'is_superuser': False,
            },
        )
        admin_user.is_staff = True
        admin_user.set_password(pwd_admin)
        admin_user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Creado' if created else 'Actualizado'} admin.estudio "
                f'(staff, password: {pwd_admin})'
            )
        )

        hoy = timezone.localdate()
        rng = random.Random(42)
        creados = 0
        actualizados = 0

        for i in range(1, total + 1):
            codigo = f'P{i:03d}'
            username = f'estudio.{codigo.lower()}'
            grupo = (
                Paciente.GRUPO_INTERVENCION
                if i <= total // 2
                else Paciente.GRUPO_CONTROL
            )
            # Mismo patrón de nombre para guiar el reemplazo por datos reales:
            # "Participante P001", "Participante P002", …
            nombre = f'Participante {codigo}'
            sexo = rng.choice([Paciente.SEXO_M, Paciente.SEXO_F, Paciente.SEXO_O])
            edad = rng.randint(45, 85)
            fecha_nac = date(hoy.year - edad, rng.randint(1, 12), rng.randint(1, 28))
            ingreso = hoy - timedelta(days=rng.randint(0, 60))

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@recordatin.local'},
            )
            user.set_password(pwd_pac)
            user.save()

            paciente, pac_created = Paciente.objects.update_or_create(
                user=user,
                defaults={
                    'codigo_estudio': codigo,
                    'nombre': nombre,
                    'apellidos': '',
                    'telefono': f'555-{1000 + i:04d}',
                    'fecha_nacimiento': fecha_nac,
                    'sexo': sexo,
                    'diagnostico_principal': rng.choice(DIAGNOSTICOS),
                    'activo': True,
                    'grupo': grupo,
                    'fecha_ingreso_estudio': ingreso,
                },
            )
            if pac_created:
                creados += 1
            else:
                actualizados += 1

        n_int = Paciente.objects.filter(
            codigo_estudio__isnull=False,
            grupo=Paciente.GRUPO_INTERVENCION,
        ).count()
        n_ctrl = Paciente.objects.filter(
            codigo_estudio__isnull=False,
            grupo=Paciente.GRUPO_CONTROL,
        ).count()

        self.stdout.write(self.style.SUCCESS(
            f'Pacientes estudio: {creados} creados, {actualizados} actualizados. '
            f'Total con código: intervención={n_int}, control={n_ctrl}.'
        ))
        self.stdout.write(
            f'Login pacientes: estudio.p001 … estudio.p{total:03d} / {pwd_pac}'
        )
        self.stdout.write('Panel investigador: /maestro/  (admin.estudio)')
