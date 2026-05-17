from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import CitaMedica, TomaMedicamento

from .decorators import paciente_required
from .services import (
    calcular_adherencia_semanal,
    historial_tomas,
    marcar_toma_como_tomada,
    recordatorios_json,
    resumen_tomas_hoy,
)


class PacienteLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('paciente:dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        if not hasattr(self.request.user, 'paciente'):
            logout(self.request)
            messages.error(
                self.request,
                'Esta cuenta no tiene un perfil de paciente asociado.',
            )
            return redirect('login')
        return response


def logout_view(request):
    logout(request)
    return redirect('login')


@paciente_required
def dashboard(request):
    paciente = request.paciente
    resumen = resumen_tomas_hoy(paciente)
    proxima_cita = CitaMedica.objects.filter(
        paciente=paciente,
        estado=CitaMedica.ESTADO_PROGRAMADA,
        fecha_hora__gte=timezone.now(),
    ).first()
    adherencia = calcular_adherencia_semanal(paciente)

    context = {
        'paciente': paciente,
        'resumen': resumen,
        'proxima_cita': proxima_cita,
        'adherencia': adherencia,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'inicio',
    }
    return render(request, 'paciente/dashboard.html', context)


@paciente_required
def medicamentos_hoy(request):
    paciente = request.paciente
    resumen = resumen_tomas_hoy(paciente)

    context = {
        'paciente': paciente,
        'resumen': resumen,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'hoy',
    }
    return render(request, 'paciente/medicamentos_hoy.html', context)


@paciente_required
@require_POST
def marcar_tomado(request, toma_id):
    paciente = request.paciente
    toma = get_object_or_404(
        TomaMedicamento,
        pk=toma_id,
        paciente=paciente,
    )
    if marcar_toma_como_tomada(toma):
        messages.success(
            request,
            f'Listo. Registramos que tomó {toma.medicamento.nombre}.',
        )
    else:
        messages.info(request, 'Esta medicina ya estaba registrada como tomada.')
    return redirect('paciente:medicamentos_hoy')


@paciente_required
def historial(request):
    paciente = request.paciente
    dias = request.GET.get('dias', '7')
    try:
        dias = int(dias)
        if dias not in (7, 30):
            dias = 7
    except ValueError:
        dias = 7

    tomas = historial_tomas(paciente, dias=dias)
    context = {
        'paciente': paciente,
        'tomas': tomas,
        'dias': dias,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'historial',
    }
    return render(request, 'paciente/historial.html', context)


@paciente_required
def citas(request):
    paciente = request.paciente
    ahora = timezone.now()
    citas_futuras = CitaMedica.objects.filter(
        paciente=paciente,
        estado=CitaMedica.ESTADO_PROGRAMADA,
        fecha_hora__gte=ahora,
    )
    citas_pasadas = CitaMedica.objects.filter(
        paciente=paciente,
    ).exclude(
        pk__in=citas_futuras.values('pk'),
    )[:10]

    context = {
        'paciente': paciente,
        'proxima_cita': citas_futuras.first(),
        'citas_futuras': citas_futuras,
        'citas_pasadas': citas_pasadas,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'citas',
    }
    return render(request, 'paciente/citas.html', context)


@paciente_required
def perfil(request):
    paciente = request.paciente
    prescripciones_activas = paciente.prescripciones.filter(activa=True).count()
    context = {
        'paciente': paciente,
        'prescripciones_activas': prescripciones_activas,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'perfil',
    }
    return render(request, 'paciente/perfil.html', context)
