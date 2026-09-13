from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    CitaMedica,
    Cuidador,
    HorarioToma,
    MedicamentoPrescrito,
    Paciente,
    Prescripcion,
    RegistroRecompensaDiaria,
    TomaMedicamento,
)
from paciente.qr import url_acceso_cuidador, url_acceso_paciente
from paciente.services import generar_tomas_del_dia

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un paciente de demostración con recetas, tomas y citas.'

    def handle(self, *args, **options):
        username = 'paciente.demo'
        password = 'demo1234'

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': 'demo@recordatin.local'},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Usuario creado: {username}'))
        else:
            user.set_password(password)
            user.save()
            self.stdout.write(f'Usuario actualizado: {username}')

        paciente, _ = Paciente.objects.update_or_create(
            user=user,
            defaults={
                'nombre': 'María',
                'apellidos': 'González López',
                'telefono': '555-123-4567',
                'fecha_nacimiento': date(1965, 3, 15),
                'diagnostico_principal': 'Diabetes mellitus tipo 2, hipertensión arterial',
                'activo': True,
                'dias_cumplidos': 3,
            },
        )

        RegistroRecompensaDiaria.objects.filter(paciente=paciente).delete()
        Prescripcion.objects.filter(paciente=paciente).delete()
        CitaMedica.objects.filter(paciente=paciente).delete()
        TomaMedicamento.objects.filter(paciente=paciente).delete()

        hoy = timezone.localdate()
        prescripcion = Prescripcion.objects.create(
            paciente=paciente,
            fecha_emision=hoy - timedelta(days=30),
            fecha_inicio=hoy - timedelta(days=30),
            medico_nombre='Dr. Carlos Ramírez',
            indicaciones_generales=(
                'Mantener dieta baja en sodio y azúcares. '
                'Tomar medicamentos con alimentos salvo indicación contraria.'
            ),
            activa=True,
        )

        medicamentos_data = [
            {
                'nombre': 'Metformina',
                'dosis': '850 mg',
                'instrucciones': 'Tomar con el desayuno y la cena.',
                'horarios': [time(8, 0), time(20, 0)],
            },
            {
                'nombre': 'Losartán',
                'dosis': '50 mg',
                'instrucciones': 'Tomar en ayunas por la mañana.',
                'horarios': [time(7, 30)],
            },
            {
                'nombre': 'Atorvastatina',
                'dosis': '20 mg',
                'instrucciones': 'Tomar por la noche antes de dormir.',
                'horarios': [time(22, 0)],
            },
        ]

        for med_data in medicamentos_data:
            horarios = med_data.pop('horarios')
            medicamento = MedicamentoPrescrito.objects.create(
                prescripcion=prescripcion,
                via=MedicamentoPrescrito.VIA_ORAL,
                activo=True,
                **med_data,
            )
            for hora in horarios:
                HorarioToma.objects.create(
                    medicamento=medicamento,
                    hora=hora,
                    dias_semana=[],
                )

        generar_tomas_del_dia(paciente, hoy)

        for dias_atras in range(1, 8):
            fecha = hoy - timedelta(days=dias_atras)
            generar_tomas_del_dia(paciente, fecha)
            tomas = TomaMedicamento.objects.filter(paciente=paciente, fecha=fecha)
            for i, toma in enumerate(tomas):
                if i % 4 != 3:
                    toma.estado = TomaMedicamento.ESTADO_TOMADO
                    dt = timezone.make_aware(
                        datetime.combine(fecha, toma.hora_programada)
                    )
                    toma.hora_registrada = dt + timedelta(minutes=5)
                    toma.a_tiempo = True
                    toma.save()
                elif i % 4 == 2:
                    toma.estado = TomaMedicamento.ESTADO_OMITIDO
                    toma.save()

        tz = timezone.get_current_timezone()
        CitaMedica.objects.create(
            paciente=paciente,
            fecha_hora=timezone.make_aware(
                datetime.combine(hoy + timedelta(days=14), time(10, 30)),
                tz,
            ),
            lugar='Hospital General — Consultorio 204',
            especialidad='Endocrinología',
            motivo='Control trimestral de diabetes e hipertensión',
            estado=CitaMedica.ESTADO_PROGRAMADA,
        )
        CitaMedica.objects.create(
            paciente=paciente,
            fecha_hora=timezone.make_aware(
                datetime.combine(hoy - timedelta(days=45), time(9, 0)),
                tz,
            ),
            lugar='Centro de Salud Norte',
            especialidad='Medicina interna',
            motivo='Revisión de tratamiento',
            estado=CitaMedica.ESTADO_COMPLETADA,
        )

        cuidador, _ = Cuidador.objects.update_or_create(
            paciente=paciente,
            token_acceso='demo-cuidador-token-fijo-seed',
            defaults={
                'nombre': 'Ana (familiar demo)',
                'activo': True,
            },
        )

        self.stdout.write(self.style.SUCCESS('Datos de demostración creados.'))
        self.stdout.write(f'  Usuario (respaldo técnico): {username}')
        self.stdout.write(f'  Contraseña: {password}')
        self.stdout.write(f'  Paciente: {paciente}')
        if not paciente.token_acceso:
            paciente.save()
        self.stdout.write(f'  Acceso QR paciente: {url_acceso_paciente(paciente)}')
        self.stdout.write(f'  Acceso QR cuidador: {url_acceso_cuidador(cuidador)}')
