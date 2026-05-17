from django.conf import settings
from django.db import models


class Paciente(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paciente',
    )
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    diagnostico_principal = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'

    def __str__(self):
        return f'{self.nombre} {self.apellidos}'


class Prescripcion(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='prescripciones',
    )
    fecha_emision = models.DateField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    medico_nombre = models.CharField(max_length=200)
    indicaciones_generales = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Prescripción'
        verbose_name_plural = 'Prescripciones'
        ordering = ['-fecha_emision']

    def __str__(self):
        return f'Prescripción {self.fecha_emision} — {self.paciente}'


class MedicamentoPrescrito(models.Model):
    VIA_ORAL = 'oral'
    VIA_SUBLINGUAL = 'sublingual'
    VIA_TOPICA = 'topica'
    VIA_INYECTABLE = 'inyectable'
    VIA_CHOICES = [
        (VIA_ORAL, 'Oral'),
        (VIA_SUBLINGUAL, 'Sublingual'),
        (VIA_TOPICA, 'Tópica'),
        (VIA_INYECTABLE, 'Inyectable'),
    ]

    prescripcion = models.ForeignKey(
        Prescripcion,
        on_delete=models.CASCADE,
        related_name='medicamentos',
    )
    nombre = models.CharField(max_length=200)
    dosis = models.CharField(max_length=100)
    via = models.CharField(max_length=20, choices=VIA_CHOICES, default=VIA_ORAL)
    instrucciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Medicamento prescrito'
        verbose_name_plural = 'Medicamentos prescritos'

    def __str__(self):
        return f'{self.nombre} ({self.dosis})'

    @property
    def paciente(self):
        return self.prescripcion.paciente


class HorarioToma(models.Model):
    medicamento = models.ForeignKey(
        MedicamentoPrescrito,
        on_delete=models.CASCADE,
        related_name='horarios',
    )
    hora = models.TimeField()
    dias_semana = models.JSONField(
        default=list,
        help_text='Lista de días: 0=lunes … 6=domingo. Vacío = todos los días.',
    )

    class Meta:
        verbose_name = 'Horario de toma'
        verbose_name_plural = 'Horarios de toma'
        ordering = ['hora']

    def __str__(self):
        return f'{self.medicamento.nombre} a las {self.hora.strftime("%H:%M")}'

    def aplica_en_dia(self, weekday):
        if not self.dias_semana:
            return True
        return weekday in self.dias_semana


class TomaMedicamento(models.Model):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_TOMADO = 'tomado'
    ESTADO_OMITIDO = 'omitido'
    ESTADO_TARDIO = 'tardio'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_TOMADO, 'Tomado'),
        (ESTADO_OMITIDO, 'Omitido'),
        (ESTADO_TARDIO, 'Tardío'),
    ]

    medicamento = models.ForeignKey(
        MedicamentoPrescrito,
        on_delete=models.CASCADE,
        related_name='tomas',
    )
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='tomas',
    )
    fecha = models.DateField()
    hora_programada = models.TimeField()
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDIENTE,
    )
    hora_registrada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Toma de medicamento'
        verbose_name_plural = 'Tomas de medicamento'
        ordering = ['fecha', 'hora_programada']
        constraints = [
            models.UniqueConstraint(
                fields=['medicamento', 'fecha', 'hora_programada'],
                name='unique_toma_por_horario',
            ),
        ]

    def __str__(self):
        return f'{self.medicamento.nombre} — {self.fecha} {self.hora_programada}'


class CitaMedica(models.Model):
    ESTADO_PROGRAMADA = 'programada'
    ESTADO_COMPLETADA = 'completada'
    ESTADO_CANCELADA = 'cancelada'
    ESTADO_CHOICES = [
        (ESTADO_PROGRAMADA, 'Programada'),
        (ESTADO_COMPLETADA, 'Completada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='citas',
    )
    fecha_hora = models.DateTimeField()
    lugar = models.CharField(max_length=255)
    especialidad = models.CharField(max_length=150)
    motivo = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_PROGRAMADA,
    )

    class Meta:
        verbose_name = 'Cita médica'
        verbose_name_plural = 'Citas médicas'
        ordering = ['fecha_hora']

    def __str__(self):
        return f'{self.especialidad} — {self.fecha_hora:%d/%m/%Y %H:%M}'
