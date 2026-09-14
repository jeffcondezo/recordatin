import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def _subscription_info(suscripcion):
    return {
        'endpoint': suscripcion.endpoint,
        'keys': {
            'p256dh': suscripcion.p256dh,
            'auth': suscripcion.auth,
        },
    }


def enviar_push(
    suscripcion,
    titulo,
    cuerpo,
    url='/paciente/medicamentos/hoy/',
    tag='recordatin-alarma',
    toma_id=None,
    demo=False,
):
    payload = {
        'title': titulo,
        'body': cuerpo,
        'url': url,
        'tag': tag,
        'icon': '/static/paciente/img/icon-192.png',
        'badge': '/static/paciente/img/badge-96.png',
        'vibrate': [300, 100, 300, 100, 300],
        'tomaId': toma_id,
        'demo': bool(demo),
    }
    if toma_id or demo:
        payload['actions'] = [
            {'action': 'tomar', 'title': 'Ya lo tomé'},
        ]
    try:
        webpush(
            subscription_info=_subscription_info(suscripcion),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': settings.VAPID_CLAIMS_EMAIL},
        )
        return True
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else None
        logger.warning('Web push falló (%s): %s', status, exc)
        if status in (404, 410):
            suscripcion.activo = False
            suscripcion.save(update_fields=['activo'])
        return False


def enviar_push_paciente(
    paciente,
    titulo,
    cuerpo,
    url='/paciente/medicamentos/hoy/',
    tag='recordatin-alarma',
    toma_id=None,
    demo=False,
):
    enviados = 0
    for suscripcion in paciente.push_subscriptions.filter(activo=True, cuidador__isnull=True):
        if enviar_push(
            suscripcion,
            titulo,
            cuerpo,
            url=url,
            tag=tag,
            toma_id=toma_id,
            demo=demo,
        ):
            enviados += 1
    return enviados


def enviar_push_cuidadores(paciente, titulo, cuerpo, url='/paciente/cuidador/', tag='recordatin-cuidador'):
    enviados = 0
    for suscripcion in paciente.push_subscriptions.filter(activo=True, cuidador__isnull=False):
        # Cuidadores: sin botón de toma (es del paciente)
        if enviar_push(suscripcion, titulo, cuerpo, url=url, tag=tag, toma_id=None, demo=False):
            enviados += 1
    return enviados
