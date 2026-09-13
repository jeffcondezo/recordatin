import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import CitaMedica, Cuidador, SuscripcionPush

from .cuidador_auth import cerrar_sesion, vincular_sesion
from .decorators import cuidador_required
from .forms import CitaMedicaCuidadorForm
from .services import resumen_tomas_hoy


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def entrar_cuidador_por_qr(request, token):
    cuidador = (
        Cuidador.objects.filter(token_acceso=token, activo=True)
        .select_related('paciente')
        .first()
    )
    if cuidador is None or not cuidador.paciente.activo:
        return render(request, 'paciente/cuidador/entrada_error.html', status=404)

    vincular_sesion(request, cuidador)
    messages.success(
        request,
        f'Bienvenido/a. Está cuidando a {cuidador.paciente.nombre}.',
    )
    return redirect('paciente:cuidador_panel')


@cuidador_required
def cuidador_panel(request):
    paciente = request.paciente
    resumen = resumen_tomas_hoy(paciente)
    context = {
        'cuidador': request.cuidador,
        'paciente': paciente,
        'resumen': resumen,
        'nav_active': 'inicio',
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
    return render(request, 'paciente/cuidador/panel.html', context)


@cuidador_required
def cuidador_citas(request):
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
    )[:15]

    context = {
        'cuidador': request.cuidador,
        'paciente': paciente,
        'proxima_cita': citas_futuras.first(),
        'citas_futuras': citas_futuras,
        'citas_pasadas': citas_pasadas,
        'nav_active': 'citas',
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
    return render(request, 'paciente/cuidador/citas_list.html', context)


@cuidador_required
def cuidador_cita_nueva(request):
    paciente = request.paciente
    if request.method == 'POST':
        form = CitaMedicaCuidadorForm(request.POST, crear=True)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.paciente = paciente
            cita.estado = CitaMedica.ESTADO_PROGRAMADA
            cita.save()
            messages.success(request, 'Cita médica agregada correctamente.')
            return redirect('paciente:cuidador_citas')
    else:
        form = CitaMedicaCuidadorForm(crear=True)

    context = {
        'cuidador': request.cuidador,
        'paciente': paciente,
        'form': form,
        'titulo': 'Nueva cita médica',
        'nav_active': 'citas',
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
    return render(request, 'paciente/cuidador/cita_form.html', context)


@cuidador_required
def cuidador_cita_editar(request, cita_id):
    paciente = request.paciente
    cita = get_object_or_404(
        CitaMedica,
        pk=cita_id,
        paciente=paciente,
        estado=CitaMedica.ESTADO_PROGRAMADA,
    )
    if request.method == 'POST':
        form = CitaMedicaCuidadorForm(request.POST, instance=cita, crear=False)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cita actualizada correctamente.')
            return redirect('paciente:cuidador_citas')
    else:
        form = CitaMedicaCuidadorForm(instance=cita, crear=False)

    context = {
        'cuidador': request.cuidador,
        'paciente': paciente,
        'form': form,
        'cita': cita,
        'titulo': 'Editar cita médica',
        'nav_active': 'citas',
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
    return render(request, 'paciente/cuidador/cita_form.html', context)


@cuidador_required
@require_POST
def cuidador_cita_cancelar(request, cita_id):
    paciente = request.paciente
    cita = get_object_or_404(
        CitaMedica,
        pk=cita_id,
        paciente=paciente,
        estado=CitaMedica.ESTADO_PROGRAMADA,
    )
    cita.estado = CitaMedica.ESTADO_CANCELADA
    cita.save(update_fields=['estado'])
    messages.success(request, 'Cita cancelada.')
    return redirect('paciente:cuidador_citas')


@cuidador_required
@require_POST
def cuidador_salir(request):
    cerrar_sesion(request)
    return render(request, 'paciente/cuidador/salir.html')


@cuidador_required
@require_POST
def cuidador_push_subscribe(request):
    data = _json_body(request)
    if not data:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    endpoint = data.get('endpoint')
    keys = data.get('keys') or {}
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    if not endpoint or not p256dh or not auth:
        return JsonResponse({'ok': False, 'error': 'Suscripción incompleta'}, status=400)

    SuscripcionPush.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'paciente': request.paciente,
            'cuidador': request.cuidador,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
            'activo': True,
        },
    )
    return JsonResponse({'ok': True})


@cuidador_required
@require_POST
def cuidador_push_unsubscribe(request):
    data = _json_body(request) or {}
    endpoint = data.get('endpoint')
    qs = SuscripcionPush.objects.filter(
        paciente=request.paciente,
        cuidador=request.cuidador,
    )
    if endpoint:
        qs.filter(endpoint=endpoint).update(activo=False)
    else:
        qs.update(activo=False)
    return JsonResponse({'ok': True})
