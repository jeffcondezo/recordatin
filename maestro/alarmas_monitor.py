from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from core.models import TomaMedicamento
from paciente.sms import normalizar_msisdn


def _diagnostico_toma(toma, ahora):
    """Interpreta el estado del recordatorio (SMS o push según configuración)."""
    canal = getattr(settings, 'NOTIFICACIONES_CANAL', 'sms')
    programada = timezone.make_aware(
        datetime.combine(toma.fecha, toma.hora_programada),
        timezone.get_current_timezone(),
    )
    telefono = (toma.paciente.telefono or '').strip()
    msisdn = normalizar_msisdn(telefono) if telefono else None
    anticipo_max = getattr(settings, 'SMS_ANTICIPO_MAX_MINUTOS', None)
    if anticipo_max is None:
        from paciente.constants import SMS_ANTICIPO_MAX_MINUTOS as anticipo_max

    if toma.alarma_enviada_at:
        if canal == 'sms':
            return 'enviada', f'SMS enviado ({toma.alarma_enviada_at.strftime("%H:%M:%S")})'
        return 'enviada', 'Push enviado por el servidor'

    if canal == 'sms':
        inicio_envio = programada - timedelta(minutes=anticipo_max)
        if ahora < inicio_envio:
            mins = int((inicio_envio - ahora).total_seconds() // 60)
            return 'pendiente_hora', f'SMS se enviará ~{anticipo_max} min antes (faltan ~{mins} min)'
        if ahora > programada:
            if not telefono:
                return 'sin_dispositivo', 'Sin teléfono registrado'
            if not msisdn:
                return 'sin_dispositivo', f'Teléfono inválido ({telefono})'
            return 'no_enviada', 'Ventana de anticipo pasó y no hay envío — revise cron o LabsMobile'
        # ahora entre inicio_envio y programada
        if not telefono:
            return 'sin_dispositivo', 'Sin teléfono registrado'
        if not msisdn:
            return 'sin_dispositivo', f'Teléfono inválido ({telefono})'
        return 'esperando_cron', 'En ventana de anticipo; el cron debería enviar el SMS pronto'

    if ahora < programada:
        return 'pendiente_hora', 'Aún no es la hora'

    ventana = 'fuera' if ahora > programada + timedelta(minutes=15) else 'en_ventana'

    # Canal push (legacy)
    from core.models import SuscripcionPush
    n_subs = SuscripcionPush.objects.filter(
        paciente=toma.paciente,
        activo=True,
        cuidador__isnull=True,
    ).count()
    if n_subs == 0:
        return 'sin_dispositivo', 'Sin suscripción push activa'
    if ventana == 'fuera':
        return 'no_enviada', 'Hora pasó y no hay envío — revise el cron o fallos de push'
    return 'esperando_cron', 'Hora cumplida; el cron debería enviarla en esta ventana'


def tomas_alarmas_hoy(paciente=None, fecha=None):
    if fecha is None:
        fecha = timezone.localdate()
    ahora = timezone.localtime()

    qs = (
        TomaMedicamento.objects.filter(fecha=fecha)
        .select_related('medicamento', 'paciente', 'paciente__user')
        .order_by('hora_programada', 'paciente__codigo_estudio', 'pk')
    )
    if paciente is not None:
        qs = qs.filter(paciente=paciente)

    filas = []
    for toma in qs:
        codigo, texto = _diagnostico_toma(toma, ahora)
        telefono = (toma.paciente.telefono or '').strip()
        filas.append({
            'toma': toma,
            'n_subs': 1 if telefono else 0,
            'telefono': telefono or '—',
            'diag_codigo': codigo,
            'diag_texto': texto,
        })
    return filas


def resumen_alarmas_hoy(fecha=None):
    filas = tomas_alarmas_hoy(fecha=fecha)
    contadores = {
        'total': len(filas),
        'enviadas': 0,
        'pendiente_hora': 0,
        'sin_dispositivo': 0,
        'no_enviada': 0,
        'esperando_cron': 0,
        'otras': 0,
    }
    for f in filas:
        key = f['diag_codigo']
        if key == 'enviada':
            contadores['enviadas'] += 1
        elif key in contadores:
            contadores[key] += 1
        else:
            contadores['otras'] += 1
    return filas, contadores
