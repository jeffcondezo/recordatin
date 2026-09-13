from django.utils import timezone

from core.models import Cuidador

SESSION_KEY = 'cuidador_id'


def obtener_cuidador_sesion(session):
    cuidador_id = session.get(SESSION_KEY)
    if not cuidador_id:
        return None
    return (
        Cuidador.objects.filter(pk=cuidador_id, activo=True)
        .select_related('paciente')
        .first()
    )


def vincular_sesion(request, cuidador):
    request.session[SESSION_KEY] = cuidador.pk
    cuidador.ultimo_acceso = timezone.now()
    cuidador.save(update_fields=['ultimo_acceso'])


def cerrar_sesion(request):
    request.session.pop(SESSION_KEY, None)
