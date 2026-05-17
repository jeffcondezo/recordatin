from .services import obtener_paciente, recordatorios_json, resumen_tomas_hoy


def paciente_context(request):
    if not request.user.is_authenticated:
        return {}
    paciente = obtener_paciente(request.user)
    if paciente is None:
        return {}
    resumen = resumen_tomas_hoy(paciente)
    return {
        'resumen': resumen,
        'recordatorios': recordatorios_json(paciente),
    }
