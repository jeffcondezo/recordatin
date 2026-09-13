from datetime import datetime, timedelta

from django.utils import timezone

from core.models import (
    MedicamentoPrescrito,
    TomaMedicamento,
)

from .constants import VENTANA_MINUTOS


def obtener_paciente(user):
    if not user.is_authenticated:
        return None
    return getattr(user, 'paciente', None)


def medicamentos_activos(paciente):
    return MedicamentoPrescrito.objects.filter(
        activo=True,
        prescripcion__paciente=paciente,
        prescripcion__activa=True,
    ).select_related('prescripcion')


def generar_tomas_del_dia(paciente, fecha=None):
    if fecha is None:
        fecha = timezone.localdate()

    weekday = fecha.weekday()
    creadas = 0

    for medicamento in medicamentos_activos(paciente):
        for horario in medicamento.horarios.all():
            if not horario.aplica_en_dia(weekday):
                continue
            _, created = TomaMedicamento.objects.get_or_create(
                medicamento=medicamento,
                paciente=paciente,
                fecha=fecha,
                hora_programada=horario.hora,
                defaults={'estado': TomaMedicamento.ESTADO_PENDIENTE},
            )
            if created:
                creadas += 1

    return creadas


def tomas_del_dia(paciente, fecha=None):
    if fecha is None:
        fecha = timezone.localdate()
    generar_tomas_del_dia(paciente, fecha)
    return TomaMedicamento.objects.filter(
        paciente=paciente,
        fecha=fecha,
    ).select_related('medicamento').order_by('hora_programada')


def _hora_programada_aware(toma):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.combine(toma.fecha, toma.hora_programada),
        tz,
    )


def ventana_recompensa_cerrada(toma):
    """True si ya pasaron los 15 min de la hora programada (no cuenta para el día)."""
    if toma.estado == TomaMedicamento.ESTADO_TOMADO:
        return toma.a_tiempo is False
    return timezone.now() > _hora_programada_aware(toma) + timedelta(minutes=VENTANA_MINUTOS)


def marcar_toma_como_tomada(toma):
    if toma.estado == TomaMedicamento.ESTADO_TOMADO:
        return False, toma.a_tiempo is True

    ahora = timezone.now()
    programada = _hora_programada_aware(toma)
    limite = programada + timedelta(minutes=VENTANA_MINUTOS)
    a_tiempo = ahora <= limite

    toma.estado = TomaMedicamento.ESTADO_TOMADO
    toma.hora_registrada = ahora
    toma.a_tiempo = a_tiempo
    toma.save(update_fields=['estado', 'hora_registrada', 'a_tiempo'])
    return True, a_tiempo


def actualizar_estados_tardios(tomas):
    ahora = timezone.localtime()
    hora_actual = ahora.time()
    for toma in tomas:
        if (
            toma.estado == TomaMedicamento.ESTADO_PENDIENTE
            and toma.hora_programada < hora_actual
        ):
            toma.estado = TomaMedicamento.ESTADO_TARDIO
            toma.save(update_fields=['estado'])


def _formatear_minutos(minutos):
    if minutos == 1:
        return '1 minuto'
    return f'{minutos} minutos'


def _formatear_horas(horas):
    if horas == 1:
        return '1 hora'
    return f'{horas} horas'


def texto_tiempo_toma(toma):
    """Texto legible del tiempo hasta (o desde) la hora programada."""
    if toma.estado == TomaMedicamento.ESTADO_TOMADO:
        return 'Ya tomado'

    programada = _hora_programada_aware(toma)
    ahora = timezone.localtime()
    diff_seg = int((programada - ahora).total_seconds())
    limite = programada + timedelta(minutes=VENTANA_MINUTOS)

    if ventana_recompensa_cerrada(toma):
        return 'Puede registrarla aunque haya pasado la hora'

    if abs(diff_seg) < 60:
        return 'Ahora mismo — regístrela en cuanto la tome'

    if diff_seg > 0:
        minutos = diff_seg // 60
        if minutos < 60:
            return f'En {_formatear_minutos(minutos)}'
        horas = minutos // 60
        mins_resto = minutos % 60
        if mins_resto == 0:
            return f'En {_formatear_horas(horas)}'
        return f'En {_formatear_horas(horas)} y {_formatear_minutos(mins_resto)}'

    minutos = abs(diff_seg) // 60
    if ahora <= limite:
        if minutos < 60:
            return f'Hace {_formatear_minutos(minutos)} — aún a tiempo para registrarla'
        horas = minutos // 60
        mins_resto = minutos % 60
        if mins_resto == 0:
            return f'Hace {_formatear_horas(horas)} — aún a tiempo para registrarla'
        return (
            f'Hace {_formatear_horas(horas)} y {_formatear_minutos(mins_resto)} '
            '— aún a tiempo para registrarla'
        )

    if minutos < 60:
        return f'Hace {_formatear_minutos(minutos)}'
    horas = minutos // 60
    mins_resto = minutos % 60
    if mins_resto == 0:
        return f'Hace {_formatear_horas(horas)}'
    return f'Hace {_formatear_horas(horas)} y {_formatear_minutos(mins_resto)}'


def clasificar_toma(toma):
    ahora = timezone.localtime()
    hora_actual = ahora.time()

    if toma.estado == TomaMedicamento.ESTADO_TOMADO:
        return 'tomado'
    if toma.estado == TomaMedicamento.ESTADO_TARDIO:
        return 'atrasado'
    if toma.estado == TomaMedicamento.ESTADO_OMITIDO:
        return 'omitido'
    if toma.hora_programada > hora_actual:
        return 'proximo'
    if toma.hora_programada <= hora_actual:
        return 'atrasado'
    return 'pendiente'


def resumen_tomas_hoy(paciente, fecha=None):
    tomas = list(tomas_del_dia(paciente, fecha))
    actualizar_estados_tardios(tomas)
    for toma in tomas:
        toma.etiqueta = clasificar_toma(toma)
        toma.tiempo_texto = texto_tiempo_toma(toma)
        toma.ventana_cerrada = ventana_recompensa_cerrada(toma)

    pendientes = sum(1 for t in tomas if t.estado in (
        TomaMedicamento.ESTADO_PENDIENTE,
        TomaMedicamento.ESTADO_TARDIO,
    ))
    tomadas = sum(1 for t in tomas if t.estado == TomaMedicamento.ESTADO_TOMADO)
    tardias_pendientes = sum(
        1 for t in tomas
        if t.estado in (TomaMedicamento.ESTADO_PENDIENTE, TomaMedicamento.ESTADO_TARDIO)
        and t.ventana_cerrada
    )
    total = len(tomas)

    return {
        'tomas': tomas,
        'pendientes': pendientes,
        'tomadas': tomadas,
        'total': total,
        'tardias_pendientes': tardias_pendientes,
    }


def calcular_adherencia_semanal(paciente):
    hoy = timezone.localdate()
    inicio = hoy - timedelta(days=6)
    tomas = TomaMedicamento.objects.filter(
        paciente=paciente,
        fecha__gte=inicio,
        fecha__lte=hoy,
    )
    total = tomas.count()
    if total == 0:
        return 0
    tomadas = tomas.filter(estado=TomaMedicamento.ESTADO_TOMADO).count()
    return round((tomadas / total) * 100)


def historial_tomas(paciente, dias=7):
    hoy = timezone.localdate()
    inicio = hoy - timedelta(days=dias - 1)
    return TomaMedicamento.objects.filter(
        paciente=paciente,
        fecha__gte=inicio,
        fecha__lte=hoy,
    ).select_related('medicamento').order_by('-fecha', '-hora_programada')


def recordatorios_json(paciente, fecha=None):
    if fecha is None:
        fecha = timezone.localdate()
    resumen = resumen_tomas_hoy(paciente, fecha)
    tz = timezone.get_current_timezone()
    items = []
    for toma in resumen['tomas']:
        if toma.estado == TomaMedicamento.ESTADO_TOMADO:
            continue
        programada = timezone.make_aware(
            datetime.combine(fecha, toma.hora_programada),
            tz,
        )
        items.append({
            'id': toma.pk,
            'nombre': toma.medicamento.nombre,
            'dosis': toma.medicamento.dosis,
            'hora': toma.hora_programada.strftime('%H:%M'),
            'fecha': fecha.isoformat(),
            'at_ms': int(programada.timestamp() * 1000),
        })
    return items
