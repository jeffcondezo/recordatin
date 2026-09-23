import base64

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.mmas8 import LIKERT8_CHOICES, evaluacion_para, puntuar_respuestas
from core.models import EvaluacionMMAS8, MedicamentoPrescrito, Paciente, TomaMedicamento
from paciente.forms_mmas8 import MMAS8Form, initial_desde_evaluacion, respuestas_desde_form
from paciente.qr import generar_imagen_qr, url_acceso_paciente
from paciente.services import generar_tomas_del_dia, medicamentos_activos

from .alarmas_monitor import resumen_alarmas_hoy, tomas_alarmas_hoy
from .decorators import maestro_required
from .forms import MedicamentoMaestroForm, PacienteEstudioForm, guardar_medicamento
from .metricas import enriquecer_pacientes


def _respuestas_legibles(evaluacion):
    if not evaluacion:
        return []
    likert = dict(LIKERT8_CHOICES)
    filas = []
    from core.mmas8 import ITEMS_MMAS8
    for clave, texto, tipo in ITEMS_MMAS8:
        raw = evaluacion.respuestas.get(clave)
        if tipo == 'likert8':
            valor = likert.get(int(raw), raw)
        else:
            valor = 'Sí' if raw == 'si' else 'No' if raw == 'no' else raw
        filas.append({'texto': texto, 'valor': valor})
    return filas


class MaestroLoginView(LoginView):
    template_name = 'maestro/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('maestro:panel')

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_staff:
            messages.error(
                self.request,
                'Esta cuenta no es de administrador del estudio.',
            )
            return self.form_invalid(form)
        return super().form_valid(form)


def logout_maestro(request):
    logout(request)
    return redirect('maestro:login')


@maestro_required
def panel(request):
    qs = Paciente.objects.select_related('user').order_by('codigo_estudio', 'nombre')

    q = (request.GET.get('q') or '').strip()
    grupo = (request.GET.get('grupo') or '').strip()
    mmas = (request.GET.get('mmas') or '').strip()

    if q:
        qs = qs.filter(
            Q(codigo_estudio__icontains=q)
            | Q(nombre__icontains=q)
            | Q(apellidos__icontains=q)
            | Q(user__username__icontains=q)
        )
    if grupo in (
        Paciente.GRUPO_INTERVENCION,
        Paciente.GRUPO_CONTROL,
        Paciente.GRUPO_NO_DEFINIDO,
    ):
        qs = qs.filter(grupo=grupo)

    basal = EvaluacionMMAS8.objects.filter(
        paciente=OuterRef('pk'),
        momento=EvaluacionMMAS8.MOMENTO_BASAL,
    )
    seguimiento = EvaluacionMMAS8.objects.filter(
        paciente=OuterRef('pk'),
        momento=EvaluacionMMAS8.MOMENTO_SEGUIMIENTO,
    )
    qs = qs.annotate(
        tiene_basal=Exists(basal),
        tiene_seguimiento=Exists(seguimiento),
    )

    if mmas == 'sin_basal':
        qs = qs.filter(tiene_basal=False)
    elif mmas == 'sin_seguimiento':
        qs = qs.filter(tiene_seguimiento=False)
    elif mmas == 'completo':
        qs = qs.filter(tiene_basal=True, tiene_seguimiento=True)

    total = Paciente.objects.count()
    n_int = Paciente.objects.filter(grupo=Paciente.GRUPO_INTERVENCION).count()
    n_ctrl = Paciente.objects.filter(grupo=Paciente.GRUPO_CONTROL).count()
    n_nd = Paciente.objects.filter(grupo=Paciente.GRUPO_NO_DEFINIDO).count()

    pacientes = list(qs[:500])
    enriquecer_pacientes(pacientes)

    return render(request, 'maestro/panel.html', {
        'pacientes': pacientes,
        'q': q,
        'grupo': grupo,
        'mmas': mmas,
        'stats': {
            'total': total,
            'intervencion': n_int,
            'control': n_ctrl,
            'no_definido': n_nd,
        },
    })


@maestro_required
def paciente_detalle(request, paciente_id):
    paciente = get_object_or_404(Paciente.objects.select_related('user'), pk=paciente_id)

    if request.method == 'POST':
        form = PacienteEstudioForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Datos del paciente actualizados.')
            return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)
    else:
        form = PacienteEstudioForm(instance=paciente)

    basal = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)
    seguimiento = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)

    acceso_url = url_acceso_paciente(paciente, request=request)
    qr_png = generar_imagen_qr(acceso_url)
    qr_base64 = base64.b64encode(qr_png).decode('ascii')

    medicamentos = list(
        medicamentos_activos(paciente).prefetch_related('horarios')
    )

    alarmas_hoy = tomas_alarmas_hoy(paciente=paciente)
    n_push = paciente.push_subscriptions.filter(
        activo=True,
        cuidador__isnull=True,
    ).count()

    return render(request, 'maestro/paciente_detalle.html', {
        'paciente': paciente,
        'form': form,
        'basal': basal,
        'seguimiento': seguimiento,
        'basal_respuestas': _respuestas_legibles(basal),
        'seguimiento_respuestas': _respuestas_legibles(seguimiento),
        'acceso_url': acceso_url,
        'qr_base64': qr_base64,
        'medicamentos': medicamentos,
        'alarmas_hoy': alarmas_hoy,
        'n_push_activo': n_push,
    })


@maestro_required
def monitor_alarmas(request):
    """Panel para ver si el servidor generó tomas y envió push hoy."""
    hoy = timezone.localdate()
    filas, contadores = resumen_alarmas_hoy(fecha=hoy)
    filtro = (request.GET.get('estado') or '').strip()
    if filtro:
        filas = [f for f in filas if f['diag_codigo'] == filtro]

    return render(request, 'maestro/monitor_alarmas.html', {
        'hoy': hoy,
        'filas': filas,
        'contadores': contadores,
        'filtro': filtro,
        'ahora': timezone.localtime(),
    })


@maestro_required
def medicamento_nuevo(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    if request.method == 'POST':
        form = MedicamentoMaestroForm(request.POST)
        if form.is_valid():
            med = guardar_medicamento(paciente, form.cleaned_data)
            creadas = generar_tomas_del_dia(paciente)
            messages.success(
                request,
                f'Se registró {med.nombre}. Tomas de hoy generadas: {creadas}.',
            )
            return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)
    else:
        form = MedicamentoMaestroForm()

    return render(request, 'maestro/medicamento_form.html', {
        'paciente': paciente,
        'form': form,
        'titulo': 'Agregar medicamento',
    })


@maestro_required
def medicamento_editar(request, paciente_id, medicamento_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    medicamento = get_object_or_404(
        MedicamentoPrescrito,
        pk=medicamento_id,
        prescripcion__paciente=paciente,
    )
    if request.method == 'POST':
        form = MedicamentoMaestroForm(request.POST)
        if form.is_valid():
            med = guardar_medicamento(paciente, form.cleaned_data, medicamento=medicamento)
            creadas = generar_tomas_del_dia(paciente)
            messages.success(
                request,
                f'Se actualizó {med.nombre}. Nuevas tomas de hoy: {creadas}.',
            )
            return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)
    else:
        form = MedicamentoMaestroForm.from_medicamento(medicamento)

    return render(request, 'maestro/medicamento_form.html', {
        'paciente': paciente,
        'form': form,
        'medicamento': medicamento,
        'titulo': f'Editar {medicamento.nombre}',
    })


@maestro_required
@require_POST
def medicamento_desactivar(request, paciente_id, medicamento_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    medicamento = get_object_or_404(
        MedicamentoPrescrito,
        pk=medicamento_id,
        prescripcion__paciente=paciente,
    )
    medicamento.activo = False
    medicamento.save(update_fields=['activo'])
    # Quitar tomas pendientes de hoy para que no sigan en el celular ni alarmando.
    hoy = timezone.localdate()
    TomaMedicamento.objects.filter(
        medicamento=medicamento,
        paciente=paciente,
        fecha=hoy,
        estado__in=(
            TomaMedicamento.ESTADO_PENDIENTE,
            TomaMedicamento.ESTADO_TARDIO,
        ),
    ).delete()
    messages.success(request, f'{medicamento.nombre} quedó desactivado.')
    return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)


@maestro_required
def paciente_qr_png(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    acceso_url = url_acceso_paciente(paciente, request=request)
    png = generar_imagen_qr(acceso_url)
    codigo = paciente.codigo_estudio or f'id{paciente.pk}'
    response = HttpResponse(png, content_type='image/png')
    response['Content-Disposition'] = (
        f'attachment; filename="recordatin-qr-{codigo}.png"'
    )
    return response


@maestro_required
def paciente_consentimiento_firmado_pdf(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    if not paciente.tiene_consentimiento:
        messages.warning(request, 'Este paciente aún no ha firmado el consentimiento.')
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    from paciente.consentimiento_pdf_firmado import generar_pdf_consentimiento_firmado

    pdf = generar_pdf_consentimiento_firmado(paciente)
    codigo = paciente.codigo_estudio or f'id{paciente.pk}'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="consentimiento-firmado-{codigo}.pdf"'
    )
    return response


@maestro_required
@require_POST
def paciente_anular_consentimiento(request, paciente_id):
    """Borra la firma para que el paciente deba firmar de nuevo al entrar."""
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    if not paciente.tiene_consentimiento:
        messages.info(request, 'Este paciente aún no tiene consentimiento firmado.')
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    if paciente.consentimiento_firma:
        paciente.consentimiento_firma.delete(save=False)
    paciente.consentimiento_firma = None
    paciente.consentimiento_aceptado_at = None
    paciente.save(update_fields=['consentimiento_firma', 'consentimiento_aceptado_at'])
    messages.success(
        request,
        f'Se anuló el consentimiento de {paciente.nombre_completo}. '
        'La próxima vez que entre a la app deberá firmar de nuevo.',
    )
    return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)


@maestro_required
@require_POST
def paciente_activar_seguimiento_hint(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    basal = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)
    seguimiento = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)

    if not basal:
        messages.warning(
            request,
            'Este paciente aún no tiene MMAS-8 basal. '
            'Regístrela usted o pida al paciente que la complete en la app.',
        )
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    if seguimiento:
        messages.info(
            request,
            'Este paciente ya tiene MMAS-8 de seguimiento. '
            'Puede editarlo desde el botón correspondiente.',
        )
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    paciente.mmas_seguimiento_solicitado = True
    paciente.save(update_fields=['mmas_seguimiento_solicitado'])
    messages.success(
        request,
        f'Listo. La próxima vez que {paciente.nombre} entre a la app '
        'verá el cuestionario de seguimiento. '
        'También puede registrarlo usted desde «Registrar seguimiento».',
    )
    return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)


@maestro_required
def paciente_mmas8(request, paciente_id, momento):
    """Registrar o editar MMAS-8 (basal / seguimiento) desde el panel maestro."""
    if momento not in (
        EvaluacionMMAS8.MOMENTO_BASAL,
        EvaluacionMMAS8.MOMENTO_SEGUIMIENTO,
    ):
        messages.error(request, 'Momento de evaluación no válido.')
        return redirect('maestro:paciente_detalle', paciente_id=paciente_id)

    paciente = get_object_or_404(Paciente, pk=paciente_id)
    existente = evaluacion_para(paciente, momento)

    if momento == EvaluacionMMAS8.MOMENTO_SEGUIMIENTO:
        if not evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL):
            messages.warning(
                request,
                'Primero registre la evaluación basal (inicio).',
            )
            return redirect(
                'maestro:paciente_mmas8',
                paciente_id=paciente.pk,
                momento=EvaluacionMMAS8.MOMENTO_BASAL,
            )

    if request.method == 'POST':
        form = MMAS8Form(request.POST)
        if form.is_valid():
            respuestas = respuestas_desde_form(form.cleaned_data)
            puntaje, categoria = puntuar_respuestas(respuestas)
            ahora = timezone.now()
            if existente:
                existente.respuestas = respuestas
                existente.puntaje = puntaje
                existente.categoria = categoria
                existente.registrado_por = EvaluacionMMAS8.ORIGEN_ADMIN
                existente.fecha = ahora
                existente.save(
                    update_fields=[
                        'respuestas',
                        'puntaje',
                        'categoria',
                        'registrado_por',
                        'fecha',
                    ],
                )
                accion = 'actualizó'
            else:
                EvaluacionMMAS8.objects.create(
                    paciente=paciente,
                    momento=momento,
                    respuestas=respuestas,
                    puntaje=puntaje,
                    categoria=categoria,
                    registrado_por=EvaluacionMMAS8.ORIGEN_ADMIN,
                )
                accion = 'registró'

            if (
                momento == EvaluacionMMAS8.MOMENTO_SEGUIMIENTO
                and paciente.mmas_seguimiento_solicitado
            ):
                paciente.mmas_seguimiento_solicitado = False
                paciente.save(update_fields=['mmas_seguimiento_solicitado'])

            etiqueta = (
                'basal (inicio)'
                if momento == EvaluacionMMAS8.MOMENTO_BASAL
                else 'seguimiento'
            )
            messages.success(
                request,
                f'Se {accion} el MMAS-8 de {etiqueta} '
                f'(puntaje {puntaje}).',
            )
            return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)
    else:
        form = MMAS8Form(initial=initial_desde_evaluacion(existente))

    titulo = (
        'MMAS-8 basal (inicio)'
        if momento == EvaluacionMMAS8.MOMENTO_BASAL
        else 'MMAS-8 de seguimiento'
    )
    return render(request, 'maestro/mmas8_form.html', {
        'paciente': paciente,
        'form': form,
        'momento': momento,
        'titulo': titulo,
        'existente': existente,
        'editando': bool(existente),
    })
