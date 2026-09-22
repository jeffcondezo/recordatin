from datetime import datetime, time

from django import forms
from django.utils import timezone

from core.models import MedicamentoPrescrito, Paciente, Prescripcion, HorarioToma


class PacienteEstudioForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'codigo_estudio',
            'nombre',
            'dni',
            'telefono',
            'fecha_nacimiento',
            'edad',
            'sexo',
            'diagnostico_principal',
            'enfermedad_2',
            'enfermedad_3',
            'grupo',
            'fecha_ingreso_estudio',
            'activo',
        ]
        labels = {
            'nombre': 'Nombres y apellidos',
        }
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'fecha_ingreso_estudio': forms.DateInput(attrs={'type': 'date'}),
            'diagnostico_principal': forms.TextInput(),
            'enfermedad_2': forms.TextInput(),
            'enfermedad_3': forms.TextInput(),
            'edad': forms.NumberInput(attrs={'min': 0, 'max': 130}),
        }
        help_texts = {
            'edad': (
                'Se calcula sola si hay fecha de nacimiento. '
                'Si no hay fecha, ingrese la edad aquí.'
            ),
            'enfermedad_2': 'Opcional.',
            'enfermedad_3': 'Opcional.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            field.widget.attrs.setdefault('class', css)

        if self.instance and self.instance.pk and self.instance.fecha_nacimiento:
            self.fields['edad'].initial = self.instance.edad_actual
            self.fields['edad'].widget.attrs['readonly'] = True
            self.fields['edad'].help_text = (
                'Calculada automáticamente a partir de la fecha de nacimiento.'
            )

    def clean(self):
        cleaned = super().clean()
        fecha_nac = cleaned.get('fecha_nacimiento')
        if fecha_nac:
            cleaned['edad'] = Paciente.calcular_edad(fecha_nac)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Todo el nombre va en un solo campo; se vacía el legado.
        instance.apellidos = ''
        if commit:
            instance.save()
            self.save_m2m()
        return instance


def _parse_hora(valor):
    valor = (valor or '').strip()
    if not valor:
        return None
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(valor, fmt).time()
        except ValueError:
            continue
    raise forms.ValidationError(f'Hora no válida: {valor}. Use formato HH:MM.')


class MedicamentoMaestroForm(forms.Form):
    nombre = forms.CharField(max_length=200, label='Nombre del medicamento')
    dosis = forms.CharField(max_length=100, label='Dosis', help_text='Ej. 850 mg, 1 tableta')
    via = forms.ChoiceField(
        choices=MedicamentoPrescrito.VIA_CHOICES,
        initial=MedicamentoPrescrito.VIA_ORAL,
        label='Vía',
    )
    instrucciones = forms.CharField(
        required=False,
        label='Instrucciones',
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    hora_1 = forms.CharField(required=False, label='Horario 1', widget=forms.TimeInput(attrs={'type': 'time'}))
    hora_2 = forms.CharField(required=False, label='Horario 2', widget=forms.TimeInput(attrs={'type': 'time'}))
    hora_3 = forms.CharField(required=False, label='Horario 3', widget=forms.TimeInput(attrs={'type': 'time'}))
    hora_4 = forms.CharField(required=False, label='Horario 4', widget=forms.TimeInput(attrs={'type': 'time'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        horas = []
        for key in ('hora_1', 'hora_2', 'hora_3', 'hora_4'):
            raw = cleaned.get(key)
            if not raw:
                continue
            try:
                h = _parse_hora(raw)
            except forms.ValidationError as exc:
                self.add_error(key, exc)
                continue
            if h and h not in horas:
                horas.append(h)
        if not horas:
            raise forms.ValidationError('Indique al menos un horario de toma (HH:MM).')
        cleaned['horarios'] = horas
        return cleaned

    @classmethod
    def from_medicamento(cls, medicamento):
        horas = list(medicamento.horarios.order_by('hora').values_list('hora', flat=True))
        initial = {
            'nombre': medicamento.nombre,
            'dosis': medicamento.dosis,
            'via': medicamento.via,
            'instrucciones': medicamento.instrucciones,
        }
        for i, h in enumerate(horas[:4], start=1):
            initial[f'hora_{i}'] = h.strftime('%H:%M')
        return cls(initial=initial)


def obtener_o_crear_prescripcion_activa(paciente):
    prescripcion = (
        paciente.prescripciones.filter(activa=True)
        .order_by('-fecha_emision')
        .first()
    )
    if prescripcion:
        return prescripcion
    hoy = timezone.localdate()
    return Prescripcion.objects.create(
        paciente=paciente,
        fecha_emision=hoy,
        fecha_inicio=hoy,
        medico_nombre='Equipo Recordatin (estudio)',
        indicaciones_generales='Tratamiento registrado por el investigador del estudio.',
        activa=True,
    )


def guardar_medicamento(paciente, cleaned_data, medicamento=None):
    prescripcion = obtener_o_crear_prescripcion_activa(paciente)
    if medicamento is None:
        medicamento = MedicamentoPrescrito(prescripcion=prescripcion)

    medicamento.prescripcion = prescripcion
    medicamento.nombre = cleaned_data['nombre']
    medicamento.dosis = cleaned_data['dosis']
    medicamento.via = cleaned_data['via']
    medicamento.instrucciones = cleaned_data.get('instrucciones') or ''
    medicamento.activo = True
    medicamento.save()

    medicamento.horarios.all().delete()
    for hora in cleaned_data['horarios']:
        HorarioToma.objects.create(
            medicamento=medicamento,
            hora=hora,
            dias_semana=[],
        )
    return medicamento
