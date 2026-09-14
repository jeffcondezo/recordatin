"""
MMAS-8 (Morisky Medication Adherence Scale) — ítems en español y puntuación.

Ítems 1–7: Sí = 1 punto de no adherencia (excepto el 5, invertido).
Ítem 8: escala Likert 0–4 convertida a 0, 0.25, 0.5, 0.75, 1.
Puntaje total 0–8 (mayor = mejor adherencia):
  8 = alta, 6–<8 = media, <6 = baja.
"""
from decimal import Decimal

from core.models import EvaluacionMMAS8

# (clave, texto, tipo)
# tipo: 'si_no' | 'si_no_invertido' | 'likert8'
ITEMS_MMAS8 = [
    (
        'q1',
        '¿Se le olvida alguna vez tomar sus medicamentos?',
        'si_no',
    ),
    (
        'q2',
        'En las últimas 2 semanas, ¿hubo algún día en que no tomó su medicamento?',
        'si_no',
    ),
    (
        'q3',
        '¿Ha reducido o dejado de tomar su medicamento sin avisarle a su médico '
        'porque se sentía peor al tomarlo?',
        'si_no',
    ),
    (
        'q4',
        '¿Se le olvida llevarse sus medicamentos cuando viaja o sale de casa?',
        'si_no',
    ),
    (
        'q5',
        '¿Tomó su medicamento ayer?',
        'si_no_invertido',
    ),
    (
        'q6',
        'Cuando siente que su enfermedad está bajo control, '
        '¿deja de tomar su medicamento?',
        'si_no',
    ),
    (
        'q7',
        'Tomar medicamentos todos los días es una molestia real para algunas personas. '
        '¿Se siente alguna vez molesto/a por tener que cumplir con su plan de tratamiento?',
        'si_no',
    ),
    (
        'q8',
        '¿Con qué frecuencia tiene dificultad para recordar tomar todos sus medicamentos?',
        'likert8',
    ),
]

LIKERT8_CHOICES = [
    (0, 'Nunca / casi nunca'),
    (1, 'De vez en cuando'),
    (2, 'A veces'),
    (3, 'Por lo general'),
    (4, 'Todo el tiempo'),
]

LIKERT8_SCORES = {
    0: Decimal('0'),
    1: Decimal('0.25'),
    2: Decimal('0.50'),
    3: Decimal('0.75'),
    4: Decimal('1'),
}


def puntuar_respuestas(respuestas):
    """
    respuestas: dict con claves q1..q7 ('si'|'no') y q8 (int 0-4).
    Devuelve (puntaje Decimal, categoria str).
    """
    total = Decimal('0')

    for clave, _texto, tipo in ITEMS_MMAS8:
        if clave not in respuestas:
            raise ValueError(f'Falta respuesta para {clave}')

        valor = respuestas[clave]
        if tipo == 'si_no':
            # Sí = no adherencia → 0 al total de adherencia; No = 1
            total += Decimal('0') if valor == 'si' else Decimal('1')
        elif tipo == 'si_no_invertido':
            # q5: ¿Tomó ayer? Sí = adherente (1), No = 0
            total += Decimal('1') if valor == 'si' else Decimal('0')
        elif tipo == 'likert8':
            likert = int(valor)
            if likert not in LIKERT8_SCORES:
                raise ValueError('Ítem 8 inválido')
            # Escala de dificultad: mayor frecuencia resta adherencia
            total += Decimal('1') - LIKERT8_SCORES[likert]

    if total >= Decimal('8'):
        categoria = EvaluacionMMAS8.CATEGORIA_ALTA
    elif total >= Decimal('6'):
        categoria = EvaluacionMMAS8.CATEGORIA_MEDIA
    else:
        categoria = EvaluacionMMAS8.CATEGORIA_BAJA

    return total, categoria


def evaluacion_para(paciente, momento):
    return EvaluacionMMAS8.objects.filter(
        paciente=paciente,
        momento=momento,
    ).first()


def momentos_pendientes(paciente):
    pendientes = []
    if not evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL):
        pendientes.append(EvaluacionMMAS8.MOMENTO_BASAL)
    if not evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO):
        pendientes.append(EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)
    return pendientes
