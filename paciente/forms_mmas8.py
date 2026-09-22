from django import forms

from core.mmas8 import ITEMS_MMAS8, LIKERT8_CHOICES


class MMAS8Form(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for clave, texto, tipo in ITEMS_MMAS8:
            if tipo == 'likert8':
                self.fields[clave] = forms.TypedChoiceField(
                    label=texto,
                    choices=LIKERT8_CHOICES,
                    coerce=int,
                    widget=forms.RadioSelect,
                )
            else:
                self.fields[clave] = forms.ChoiceField(
                    label=texto,
                    choices=[('si', 'Sí'), ('no', 'No')],
                    widget=forms.RadioSelect,
                )


def respuestas_desde_form(cleaned_data):
    return {clave: cleaned_data[clave] for clave, _t, _tipo in ITEMS_MMAS8}


def initial_desde_evaluacion(evaluacion):
    """Valores iniciales del formulario a partir de una evaluación guardada."""
    if not evaluacion or not evaluacion.respuestas:
        return {}
    initial = {}
    for clave, _texto, tipo in ITEMS_MMAS8:
        raw = evaluacion.respuestas.get(clave)
        if raw is None:
            continue
        if tipo == 'likert8':
            initial[clave] = int(raw)
        else:
            initial[clave] = raw
    return initial
