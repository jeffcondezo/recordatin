from django.urls import reverse

from core.mmas8 import evaluacion_para, momentos_pendientes
from core.models import EvaluacionMMAS8, Paciente


def url_inicio_paciente(paciente):
    """Destino tras login/QR según consentimiento, grupo y MMAS pendiente."""
    if not paciente.tiene_consentimiento:
        return reverse('paciente:consentimiento')

    pendientes = momentos_pendientes(paciente)

    # Basal siempre primero
    if EvaluacionMMAS8.MOMENTO_BASAL in pendientes:
        return reverse('paciente:mmas8', kwargs={'momento': 'basal'})

    # Seguimiento forzado cuando el investigador lo solicita
    if (
        paciente.mmas_seguimiento_solicitado
        and EvaluacionMMAS8.MOMENTO_SEGUIMIENTO in pendientes
    ):
        return reverse('paciente:mmas8', kwargs={'momento': 'seguimiento'})

    if paciente.grupo == Paciente.GRUPO_INTERVENCION:
        return reverse('paciente:medicamentos_hoy')

    return reverse('paciente:mmas8_inicio')
