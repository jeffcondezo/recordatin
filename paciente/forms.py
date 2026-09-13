from django import forms
from django.utils import timezone

from core.models import CitaMedica


class CitaMedicaCuidadorForm(forms.ModelForm):
    class Meta:
        model = CitaMedica
        fields = ('fecha_hora', 'especialidad', 'lugar', 'motivo')
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-input',
                },
            ),
            'especialidad': forms.TextInput(attrs={'class': 'form-input'}),
            'lugar': forms.TextInput(attrs={'class': 'form-input'}),
            'motivo': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def __init__(self, *args, crear=False, **kwargs):
        self.crear = crear
        super().__init__(*args, **kwargs)
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M', '%d/%m/%Y %H:%M']
        if self.instance.pk and self.instance.fecha_hora:
            self.fields['fecha_hora'].initial = timezone.localtime(
                self.instance.fecha_hora,
            ).strftime('%Y-%m-%dT%H:%M')

    def clean_fecha_hora(self):
        fecha_hora = self.cleaned_data['fecha_hora']
        if self.crear and fecha_hora <= timezone.now():
            raise forms.ValidationError('La cita debe ser en una fecha y hora futuras.')
        return fecha_hora
