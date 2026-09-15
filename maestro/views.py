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

from core.mmas8 import LIKERT8_CHOICES, evaluacion_para
from core.models import EvaluacionMMAS8, MedicamentoPrescrito, Paciente, TomaMedicamento
from paciente.qr import generar_imagen_qr, url_acceso_paciente
from paciente.services import generar_tomas_del_dia, medicamentos_activos

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
    qs = Paciente.objects.select_related('user').order_by('codigo_estudio', 'apellidos')

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
    if grupo in (Paciente.GRUPO_INTERVENCION, Paciente.GRUPO_CONTROL):
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
@require_POST
def paciente_activar_seguimiento_hint(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    basal = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)
    seguimiento = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)

    if not basal:
        messages.warning(
            request,
            'Este paciente aún no tiene MMAS-8 basal. '
            'Primero debe completar el cuestionario de inicio.',
        )
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    if seguimiento:
        messages.info(
            request,
            'Este paciente ya completó el MMAS-8 de seguimiento.',
        )
        return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)

    paciente.mmas_seguimiento_solicitado = True
    paciente.save(update_fields=['mmas_seguimiento_solicitado'])
    messages.success(
        request,
        f'Listo. La próxima vez que {paciente.nombre} entre a la app '
        'verá el cuestionario de seguimiento para completarlo.',
    )
    return redirect('maestro:paciente_detalle', paciente_id=paciente.pk)
