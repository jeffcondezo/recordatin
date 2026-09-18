from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.models import SuscripcionPush, TomaMedicamento


def _diagnostico_toma(toma, ahora, n_subs):
    """Interpreta por qué una alarma pudo no llegar al celular."""
    programada = timezone.make_aware(
        datetime.combine(toma.fecha, toma.hora_programada),
        timezone.get_current_timezone(),
    )
    if toma.alarma_enviada_at:
        return 'enviada', 'Push enviado por el servidor'
    if ahora < programada:
        return 'pendiente_hora', 'Aún no es la hora'
    if ahora > programada + timedelta(minutes=15):
        ventana = 'fuera'
    else:
        ventana = 'en_ventana'

    if n_subs == 0:
        return 'sin_dispositivo', 'Sin suscripción push activa (el paciente debe Activar alarmas)'
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

    tomas = list(qs)
    if not tomas:
        return []

    paciente_ids = {t.paciente_id for t in tomas}
    subs = (
        SuscripcionPush.objects.filter(
            paciente_id__in=paciente_ids,
            activo=True,
            cuidador__isnull=True,
        )
        .values('paciente_id')
        .annotate(n=Count('id'))
    )
    subs_map = {row['paciente_id']: row['n'] for row in subs}

    filas = []
    for toma in tomas:
        n_subs = subs_map.get(toma.paciente_id, 0)
        codigo, texto = _diagnostico_toma(toma, ahora, n_subs)
        filas.append({
            'toma': toma,
            'n_subs': n_subs,
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
