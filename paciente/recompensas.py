from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.models import Paciente, RegistroRecompensaDiaria, TomaMedicamento

from .services import generar_tomas_del_dia, tomas_del_dia


def toma_cumple_recompensa(toma):
    return (
        toma.estado == TomaMedicamento.ESTADO_TOMADO
        and toma.a_tiempo is True
    )


def evaluar_dia(paciente, fecha):
    generar_tomas_del_dia(paciente, fecha)
    tomas = list(tomas_del_dia(paciente, fecha))

    if not tomas:
        return RegistroRecompensaDiaria.RESULTADO_SIN_TOMAS

    if all(toma_cumple_recompensa(t) for t in tomas):
        return RegistroRecompensaDiaria.RESULTADO_EXITO

    return RegistroRecompensaDiaria.RESULTADO_FALLO


def _fecha_inicio_procesamiento(paciente):
    ultimo = RegistroRecompensaDiaria.objects.filter(
        paciente=paciente,
    ).order_by('-fecha').values_list('fecha', flat=True).first()

    if ultimo:
        return ultimo + timedelta(days=1)

    primera_toma = TomaMedicamento.objects.filter(
        paciente=paciente,
    ).order_by('fecha').values_list('fecha', flat=True).first()

    if primera_toma:
        return primera_toma

    return timezone.localdate()


@transaction.atomic
def aplicar_recompensa(paciente, fecha, resultado):
    if RegistroRecompensaDiaria.objects.filter(
        paciente=paciente,
        fecha=fecha,
    ).exists():
        return None

    paciente = Paciente.objects.select_for_update().get(pk=paciente.pk)
    antes = paciente.dias_cumplidos

    if resultado == RegistroRecompensaDiaria.RESULTADO_EXITO:
        paciente.dias_cumplidos += 1
        paciente.save(update_fields=['dias_cumplidos'])
    else:
        # Fallo o sin tomas: el contador no baja; solo se registra el día.
        pass

    despues = paciente.dias_cumplidos
    registro = RegistroRecompensaDiaria.objects.create(
        paciente=paciente,
        fecha=fecha,
        resultado=resultado,
        dias_antes=antes,
        dias_despues=despues,
    )
    return registro


def procesar_recompensas_pendientes(paciente):
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    inicio = _fecha_inicio_procesamiento(paciente)

    if inicio > ayer:
        return []

    procesados = []
    fecha = inicio
    while fecha <= ayer:
        resultado = evaluar_dia(paciente, fecha)
        registro = aplicar_recompensa(paciente, fecha, resultado)
        if registro:
            procesados.append(registro)
        fecha += timedelta(days=1)

    return procesados


def ultimos_registros_recompensa(paciente, limite=3):
    return RegistroRecompensaDiaria.objects.filter(
        paciente=paciente,
    ).exclude(
        resultado=RegistroRecompensaDiaria.RESULTADO_SIN_TOMAS,
    ).order_by('-fecha')[:limite]
