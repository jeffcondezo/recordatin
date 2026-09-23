"""Métricas de seguimiento clínico para el panel maestro."""
from collections import defaultdict

from django.utils import timezone

from core.mmas8 import evaluacion_para
from core.models import EvaluacionMMAS8, MedicamentoPrescrito, TomaMedicamento
from paciente.services import medicamentos_activos


def registrar_primer_acceso(paciente):
    if paciente.primer_acceso:
        return False
    paciente.primer_acceso = timezone.now()
    paciente.save(update_fields=['primer_acceso'])
    return True


def metricas_paciente(paciente, tomas=None, basal=None, medicamentos=None):
    """Calcula métricas de un paciente. Puede recibir datos prefetched."""
    hoy = timezone.localdate()

    if basal is None:
        basal = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)

    if tomas is None:
        tomas = list(
            TomaMedicamento.objects.filter(paciente=paciente).only(
                'estado', 'a_tiempo', 'fecha', 'alarma_enviada_at',
            )
        )

    total = len(tomas)
    respondidas = sum(1 for t in tomas if t.estado == TomaMedicamento.ESTADO_TOMADO)
    a_tiempo = sum(1 for t in tomas if t.a_tiempo is True)
    sms_enviados = sum(1 for t in tomas if t.alarma_enviada_at is not None)

    por_dia = defaultdict(lambda: {'total': 0, 'respondidas': 0, 'a_tiempo': 0})
    for t in tomas:
        d = por_dia[t.fecha]
        d['total'] += 1
        if t.estado == TomaMedicamento.ESTADO_TOMADO:
            d['respondidas'] += 1
        if t.a_tiempo is True:
            d['a_tiempo'] += 1

    pcts_respuesta = []
    pcts_horario = []
    for d in por_dia.values():
        if d['total'] <= 0:
            continue
        pcts_respuesta.append(100.0 * d['respondidas'] / d['total'])
        pcts_horario.append(100.0 * d['a_tiempo'] / d['total'])

    promedio_respuesta_dia = (
        round(sum(pcts_respuesta) / len(pcts_respuesta), 1) if pcts_respuesta else None
    )
    promedio_horario_dia = (
        round(sum(pcts_horario) / len(pcts_horario), 1) if pcts_horario else None
    )

    dias_desde_basal = None
    if basal:
        dias_desde_basal = (hoy - basal.fecha.date()).days

    if medicamentos is None:
        medicamentos = list(medicamentos_activos(paciente).prefetch_related('horarios'))

    meds_info = []
    for med in medicamentos:
        horas = [h.hora.strftime('%H:%M') for h in med.horarios.all()]
        meds_info.append({
            'nombre': med.nombre,
            'dosis': med.dosis,
            'horarios': ', '.join(horas) if horas else '—',
        })

    return {
        'basal': basal,
        'basal_puntaje': basal.puntaje if basal else None,
        'basal_categoria': basal.get_categoria_display() if basal else None,
        'primer_acceso': paciente.primer_acceso,
        'dias_desde_basal': dias_desde_basal,
        'alertas_respondidas': respondidas,
        'alertas_total': total,
        'alertas_a_tiempo': a_tiempo,
        'sms_enviados': sms_enviados,
        'promedio_respuesta_dia': promedio_respuesta_dia,
        'promedio_horario_dia': promedio_horario_dia,
        'medicamentos': meds_info,
    }


def enriquecer_pacientes(pacientes):
    """Adjunta .metricas a cada paciente del listado (batch)."""
    ids = [p.pk for p in pacientes]
    if not ids:
        return pacientes

    basales = {
        e.paciente_id: e
        for e in EvaluacionMMAS8.objects.filter(
            paciente_id__in=ids,
            momento=EvaluacionMMAS8.MOMENTO_BASAL,
        )
    }

    tomas_qs = TomaMedicamento.objects.filter(paciente_id__in=ids).only(
        'paciente_id', 'estado', 'a_tiempo', 'fecha', 'alarma_enviada_at',
    )
    tomas_por = defaultdict(list)
    for t in tomas_qs:
        tomas_por[t.paciente_id].append(t)

    meds_qs = (
        MedicamentoPrescrito.objects.filter(
            activo=True,
            prescripcion__activa=True,
            prescripcion__paciente_id__in=ids,
        )
        .select_related('prescripcion')
        .prefetch_related('horarios')
    )
    meds_por = defaultdict(list)
    for m in meds_qs:
        meds_por[m.prescripcion.paciente_id].append(m)

    for p in pacientes:
        p.metricas = metricas_paciente(
            p,
            tomas=tomas_por.get(p.pk, []),
            basal=basales.get(p.pk),
            medicamentos=meds_por.get(p.pk, []),
        )
    return pacientes
