import json
import base64
from datetime import timedelta
from pathlib import Path

from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CitaMedica, Cuidador, EvaluacionMMAS8, Paciente, SuscripcionPush, TomaMedicamento

from core.models import RegistroRecompensaDiaria
from core.mmas8 import evaluacion_para, momentos_pendientes, puntuar_respuestas

from .decorators import paciente_required
from .estudio import url_inicio_paciente
from .forms_mmas8 import MMAS8Form, respuestas_desde_form
from .qr import generar_imagen_qr, url_acceso_cuidador
from .push import enviar_push_paciente
from .sms import enviar_sms_paciente, labsmobile_configurado, mensaje_recordatorio_grupo
from .recompensas import (
    procesar_recompensas_pendientes,
    ultimos_registros_recompensa,
)
from maestro.metricas import registrar_primer_acceso
from .services import (
    calcular_adherencia_semanal,
    historial_tomas,
    marcar_toma_como_tomada,
    medicamentos_activos,
    obtener_paciente,
    recordatorios_json,
    resumen_tomas_hoy,
)


def _redirigir_si_control(request):
    if request.paciente.es_control:
        return redirect(url_inicio_paciente(request.paciente))
    # Intervención con seguimiento solicitado: llevar al cuestionario
    if (
        request.paciente.mmas_seguimiento_solicitado
        and evaluacion_para(request.paciente, EvaluacionMMAS8.MOMENTO_BASAL)
        and not evaluacion_para(request.paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)
    ):
        return redirect('paciente:mmas8', momento='seguimiento')
    return None


def _contexto_dias_cumplidos(paciente, procesados=None):
    ayer = timezone.localdate() - timedelta(days=1)
    recompensa_ayer = ''
    if procesados:
        for registro in procesados:
            if registro.fecha == ayer and registro.resultado in (
                RegistroRecompensaDiaria.RESULTADO_EXITO,
                RegistroRecompensaDiaria.RESULTADO_FALLO,
            ):
                recompensa_ayer = registro.resultado

    return {
        'dias_cumplidos': paciente.dias_cumplidos,
        'recompensa_ayer': recompensa_ayer,
        'recompensas_recientes': ultimos_registros_recompensa(paciente, 7),
    }


def _notificar_recompensas_ayer(request, procesados):
    ayer = timezone.localdate() - timedelta(days=1)
    for registro in procesados:
        if registro.fecha != ayer:
            continue
        if registro.resultado == RegistroRecompensaDiaria.RESULTADO_EXITO:
            messages.success(
                request,
                '¡Ayer cumplió con todas sus medicinas a tiempo! '
                'Sumó 1 día al contador.',
            )
        elif registro.resultado == RegistroRecompensaDiaria.RESULTADO_FALLO:
            messages.warning(
                request,
                'Ayer no completó todas sus medicinas a tiempo. '
                'Ese día no suma al contador.',
            )


class PacienteLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_staff and obtener_paciente(user) is None:
            return reverse_lazy('maestro:panel')
        paciente = obtener_paciente(user)
        if paciente is not None:
            return url_inicio_paciente(paciente)
        return reverse_lazy('paciente:medicamentos_hoy')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        paciente = obtener_paciente(user)
        # Investigador: ir al panel del estudio (no requiere perfil paciente)
        if user.is_staff and paciente is None:
            return redirect('maestro:panel')
        if paciente is None:
            logout(self.request)
            messages.error(
                self.request,
                'Esta cuenta no tiene un perfil de paciente asociado. '
                'Si es investigador, entre por /maestro/login/.',
            )
            return redirect('login')
        registrar_primer_acceso(paciente)
        return response


def entrada(request):
    if request.user.is_authenticated:
        if request.user.is_staff and obtener_paciente(request.user) is None:
            return redirect('maestro:panel')
        paciente = obtener_paciente(request.user)
        if paciente is not None and paciente.activo:
            registrar_primer_acceso(paciente)
            return redirect(url_inicio_paciente(paciente))
    return render(request, 'paciente/entrada.html')


def entrar_por_qr(request, token):
    paciente = Paciente.objects.filter(token_acceso=token, activo=True).select_related('user').first()
    if paciente is None:
        return render(request, 'paciente/entrada_error.html', status=404)

    login(request, paciente.user)
    registrar_primer_acceso(paciente)
    messages.success(request, f'Bienvenido/a, {paciente.nombre}.')
    return redirect(url_inicio_paciente(paciente))


@paciente_required
def paciente_home(request):
    return redirect(url_inicio_paciente(request.paciente))


def _ruta_consentimiento_pdf():
    """PDF en static (deploy) o en la raíz del proyecto."""
    candidatos = [
        Path(settings.BASE_DIR) / 'paciente' / 'static' / 'paciente' / 'docs' / 'consentimiento.pdf',
        Path(settings.BASE_DIR) / 'consentimiento.pdf',
        Path(settings.STATIC_ROOT) / 'paciente' / 'docs' / 'consentimiento.pdf',
    ]
    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return None


@paciente_required
@cache_control(private=True, max_age=3600)
def consentimiento_pdf(request):
    ruta = _ruta_consentimiento_pdf()
    if ruta is None:
        return HttpResponse('Consentimiento no disponible.', status=404)
    response = HttpResponse(ruta.read_bytes(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="consentimiento-informado.pdf"'
    return response


@paciente_required
def consentimiento_firmado_pdf(request):
    """PDF dinámico con texto + firma del paciente + investigadores."""
    paciente = request.paciente
    if not paciente.tiene_consentimiento:
        messages.warning(request, 'Primero debe firmar el consentimiento informado.')
        return redirect('paciente:consentimiento')

    from .consentimiento_pdf_firmado import generar_pdf_consentimiento_firmado

    pdf = generar_pdf_consentimiento_firmado(paciente)
    codigo = paciente.codigo_estudio or f'id{paciente.pk}'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="consentimiento-firmado-{codigo}.pdf"'
    )
    return response


@paciente_required
def consentimiento(request):
    paciente = request.paciente
    editando = (
        request.GET.get('editar') == '1'
        or request.POST.get('editar') == '1'
    )

    # Ya firmó y no está corrigiendo → seguir el flujo normal
    if paciente.tiene_consentimiento and not editando:
        return redirect(url_inicio_paciente(paciente))

    # Corregir firma solo si ya había consentimiento
    if editando and not paciente.tiene_consentimiento:
        return redirect('paciente:consentimiento')

    if request.method == 'POST':
        firma_b64 = (request.POST.get('firma') or '').strip()
        if not firma_b64.startswith('data:image/png;base64,'):
            messages.error(request, 'Firme con el dedo en el recuadro e intente de nuevo.')
        else:
            try:
                raw = base64.b64decode(firma_b64.split(',', 1)[1])
            except Exception:
                raw = b''
            if len(raw) < 800:
                messages.error(
                    request,
                    'La firma parece vacía. Firme con el dedo en el recuadro.',
                )
            else:
                from django.core.files.base import ContentFile

                nombre_archivo = f'firma-{paciente.pk}-{timezone.now():%Y%m%d%H%M%S}.png'
                if paciente.consentimiento_firma:
                    paciente.consentimiento_firma.delete(save=False)
                paciente.consentimiento_firma.save(
                    nombre_archivo,
                    ContentFile(raw),
                    save=False,
                )
                paciente.consentimiento_aceptado_at = timezone.now()
                paciente.save(
                    update_fields=['consentimiento_firma', 'consentimiento_aceptado_at'],
                )
                if editando:
                    messages.success(request, 'Firma actualizada correctamente.')
                    return redirect('paciente:perfil')
                messages.success(
                    request,
                    'Gracias. Su consentimiento quedó registrado.',
                )
                return redirect(url_inicio_paciente(paciente))

    return render(request, 'paciente/consentimiento.html', {
        'paciente': paciente,
        'nav_active': 'perfil' if editando else None,
        'ocultar_nav': not editando,
        'editando': editando,
    })


@paciente_required
def mmas8_inicio(request):
    paciente = request.paciente
    # Si el investigador pidió el seguimiento, abrir el cuestionario de una vez
    if (
        paciente.mmas_seguimiento_solicitado
        and evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)
        and not evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)
        and request.GET.get('resultado') != EvaluacionMMAS8.MOMENTO_SEGUIMIENTO
    ):
        return redirect('paciente:mmas8', momento='seguimiento')

    pendientes = momentos_pendientes(paciente)
    basal = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL)
    seguimiento = evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_SEGUIMIENTO)

    resultado_modal = None
    momento_resultado = (request.GET.get('resultado') or '').strip()
    if momento_resultado in (
        EvaluacionMMAS8.MOMENTO_BASAL,
        EvaluacionMMAS8.MOMENTO_SEGUIMIENTO,
    ):
        eval_resultado = evaluacion_para(paciente, momento_resultado)
        if eval_resultado:
            textos = {
                EvaluacionMMAS8.CATEGORIA_ALTA: (
                    'Muy bien: está llevando su tratamiento de forma constante. '
                    'Seguir así ayuda a cuidar su salud.'
                ),
                EvaluacionMMAS8.CATEGORIA_MEDIA: (
                    'Va por buen camino. Aún puede mejorar tomando sus medicinas '
                    'todos los días a la hora indicada.'
                ),
                EvaluacionMMAS8.CATEGORIA_BAJA: (
                    'Conviene reforzar el hábito de tomar las medicinas a tiempo. '
                    'Si tiene dudas, hable con su médico o familiar de apoyo.'
                ),
            }
            resultado_modal = {
                'momento': momento_resultado,
                'momento_label': eval_resultado.get_momento_display(),
                'puntaje': eval_resultado.puntaje,
                'categoria': eval_resultado.categoria,
                'categoria_label': eval_resultado.get_categoria_display(),
                'mensaje': textos.get(eval_resultado.categoria, ''),
            }

    context = {
        'paciente': paciente,
        'basal': basal,
        'seguimiento': seguimiento,
        'pendientes': pendientes,
        'nav_active': 'mmas8',
        'es_control': paciente.es_control,
        'resultado_modal': resultado_modal,
    }
    return render(request, 'paciente/mmas8_inicio.html', context)


@paciente_required
def mmas8_formulario(request, momento):
    if momento not in (
        EvaluacionMMAS8.MOMENTO_BASAL,
        EvaluacionMMAS8.MOMENTO_SEGUIMIENTO,
    ):
        messages.error(request, 'Momento de evaluación no válido.')
        return redirect('paciente:mmas8_inicio')

    paciente = request.paciente
    existente = evaluacion_para(paciente, momento)
    if existente:
        messages.info(request, 'Esta evaluación ya fue registrada.')
        return redirect('paciente:mmas8_inicio')

    # Seguimiento solo si hay basal
    if momento == EvaluacionMMAS8.MOMENTO_SEGUIMIENTO:
        if not evaluacion_para(paciente, EvaluacionMMAS8.MOMENTO_BASAL):
            messages.warning(request, 'Primero complete la evaluación de inicio.')
            return redirect('paciente:mmas8', momento='basal')

    if request.method == 'POST':
        form = MMAS8Form(request.POST)
        if form.is_valid():
            respuestas = respuestas_desde_form(form.cleaned_data)
            puntaje, categoria = puntuar_respuestas(respuestas)
            EvaluacionMMAS8.objects.create(
                paciente=paciente,
                momento=momento,
                respuestas=respuestas,
                puntaje=puntaje,
                categoria=categoria,
                registrado_por=EvaluacionMMAS8.ORIGEN_PACIENTE,
            )
            if momento == EvaluacionMMAS8.MOMENTO_SEGUIMIENTO and paciente.mmas_seguimiento_solicitado:
                paciente.mmas_seguimiento_solicitado = False
                paciente.save(update_fields=['mmas_seguimiento_solicitado'])
            messages.success(request, '¡Gracias! Registramos su cuestionario.')
            destino = reverse('paciente:mmas8_inicio')
            return redirect(f'{destino}?{urlencode({"resultado": momento})}')
    else:
        form = MMAS8Form()

    titulo = 'Encuesta de inicio' if momento == 'basal' else 'Encuesta de seguimiento'
    return render(request, 'paciente/mmas8_form.html', {
        'paciente': paciente,
        'form': form,
        'momento': momento,
        'titulo': titulo,
        'nav_active': 'mmas8',
        'es_control': paciente.es_control,
    })


def logout_view(request):
    logout(request)
    return redirect('entrada')


@paciente_required
def dashboard(request):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    paciente = request.paciente
    procesados = procesar_recompensas_pendientes(paciente)
    _notificar_recompensas_ayer(request, procesados)
    paciente.refresh_from_db()

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
        'nav_active': 'resumen',
        **_contexto_dias_cumplidos(paciente, procesados),
    }
    return render(request, 'paciente/dashboard.html', context)


@paciente_required
def dias_cumplidos(request):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    paciente = request.paciente
    procesados = procesar_recompensas_pendientes(paciente)
    _notificar_recompensas_ayer(request, procesados)
    paciente.refresh_from_db()

    context = {
        'paciente': paciente,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': '',
        **_contexto_dias_cumplidos(paciente, procesados),
    }
    return render(request, 'paciente/dias_cumplidos.html', context)


@paciente_required
def medicamentos_hoy(request):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    paciente = request.paciente
    procesados = procesar_recompensas_pendientes(paciente)
    _notificar_recompensas_ayer(request, procesados)
    paciente.refresh_from_db()
    resumen = resumen_tomas_hoy(paciente)
    prescripcion = paciente.prescripciones.filter(activa=True).order_by('-fecha_emision').first()
    medicamentos_tratamiento = medicamentos_activos(paciente) if prescripcion else []

    context = {
        'paciente': paciente,
        'resumen': resumen,
        'prescripcion': prescripcion,
        'medicamentos_tratamiento': medicamentos_tratamiento,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'inicio',
        **_contexto_dias_cumplidos(paciente, procesados),
    }
    return render(request, 'paciente/medicamentos_hoy.html', context)


@paciente_required
@require_POST
def marcar_tomado(request, toma_id):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    paciente = request.paciente
    toma = get_object_or_404(
        TomaMedicamento,
        pk=toma_id,
        paciente=paciente,
    )
    actualizado, a_tiempo = marcar_toma_como_tomada(toma)
    nombre = toma.medicamento.nombre
    if actualizado:
        if a_tiempo:
            messages.success(
                request,
                f'¡Muy bien! Registramos que tomó {nombre}.',
            )
        else:
            messages.success(
                request,
                f'¡Gracias por registrar {nombre}! Lo importante es que se la tomó. '
                'Registrarla tarde no suma al día de hoy, pero cuidó bien de su salud.',
            )
    else:
        messages.info(request, 'Esta medicina ya estaba registrada como tomada.')
    return redirect('paciente:medicamentos_hoy')


@csrf_exempt
@paciente_required
@require_POST
def marcar_tomado_api(request, toma_id):
    """Marca una toma desde el botón de la notificación push (service worker).

    csrf_exempt: el service worker no siempre puede enviar el token CSRF;
    la sesión del paciente y el ownership de la toma bastan aquí.
    """
    if request.paciente.es_control:
        return JsonResponse({'ok': False, 'error': 'control'}, status=403)

    toma = get_object_or_404(
        TomaMedicamento,
        pk=toma_id,
        paciente=request.paciente,
    )
    actualizado, a_tiempo = marcar_toma_como_tomada(toma)
    return JsonResponse({
        'ok': True,
        'actualizado': actualizado,
        'a_tiempo': a_tiempo,
        'medicamento': toma.medicamento.nombre,
    })


@paciente_required
def marcar_tomado_desde_notif(request, toma_id):
    """Fallback GET cuando el SW no puede hacer POST con CSRF."""
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    toma = get_object_or_404(
        TomaMedicamento,
        pk=toma_id,
        paciente=request.paciente,
    )
    actualizado, a_tiempo = marcar_toma_como_tomada(toma)
    nombre = toma.medicamento.nombre
    if actualizado:
        if a_tiempo:
            messages.success(request, f'¡Muy bien! Registramos que tomó {nombre}.')
        else:
            messages.success(
                request,
                f'¡Gracias por registrar {nombre}! Lo importante es que se la tomó.',
            )
    else:
        messages.info(request, 'Esta medicina ya estaba registrada como tomada.')
    return redirect('paciente:medicamentos_hoy')


@paciente_required
def historial(request):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
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
    redir = _redirigir_si_control(request)
    if redir:
        return redir
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
def tratamiento(request):
    redir = _redirigir_si_control(request)
    if redir:
        return redir
    paciente = request.paciente
    prescripcion = paciente.prescripciones.filter(activa=True).order_by('-fecha_emision').first()
    medicamentos = (
        medicamentos_activos(paciente).prefetch_related('horarios')
        if prescripcion else []
    )

    context = {
        'paciente': paciente,
        'prescripcion': prescripcion,
        'medicamentos': medicamentos,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'tratamiento',
    }
    return render(request, 'paciente/tratamiento.html', context)


@paciente_required
def perfil(request):
    paciente = request.paciente
    prescripciones_activas = paciente.prescripciones.filter(activa=True).count()
    invitacion_cuidador = None
    invitacion_url = ''
    invitacion_qr_base64 = ''

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'invitar':
            invitacion_cuidador = Cuidador.objects.create(paciente=paciente)
            invitacion_url = url_acceso_cuidador(invitacion_cuidador, request)
            invitacion_qr_base64 = base64.b64encode(
                generar_imagen_qr(invitacion_url),
            ).decode('ascii')
            messages.success(
                request,
                'Enlace listo. Muestre este código QR a su familiar para que enlace su teléfono.',
            )
        elif action == 'revocar':
            cuidador_id = request.POST.get('cuidador_id')
            cuidador = paciente.cuidadores.filter(pk=cuidador_id, activo=True).first()
            if cuidador:
                cuidador.activo = False
                cuidador.save(update_fields=['activo'])
                SuscripcionPush.objects.filter(cuidador=cuidador).update(activo=False)
                messages.success(request, f'Ya no comparte acceso con {cuidador.nombre}.')
            else:
                messages.error(request, 'No se encontró ese familiar.')

    cuidadores_activos = paciente.cuidadores.filter(activo=True).order_by('-vinculado_en')

    context = {
        'paciente': paciente,
        'prescripciones_activas': prescripciones_activas,
        'cuidadores_activos': cuidadores_activos,
        'invitacion_cuidador': invitacion_cuidador,
        'invitacion_url': invitacion_url,
        'invitacion_qr_base64': invitacion_qr_base64,
        'recordatorios': recordatorios_json(paciente),
        'nav_active': 'perfil',
        **_contexto_dias_cumplidos(paciente),
    }
    return render(request, 'paciente/perfil.html', context)


_STATIC_PACIENTE = Path(settings.BASE_DIR) / 'paciente' / 'static' / 'paciente'


@cache_control(no_cache=True, must_revalidate=True)
def service_worker(request):
    path = _STATIC_PACIENTE / 'sw.js'
    return HttpResponse(
        path.read_text(encoding='utf-8'),
        content_type='application/javascript',
    )


@cache_control(max_age=86400, public=True)
def web_manifest(request):
    path = _STATIC_PACIENTE / 'manifest.webmanifest'
    return HttpResponse(
        path.read_text(encoding='utf-8'),
        content_type='application/manifest+json',
    )


@cache_control(max_age=3600, public=True)
def android_asset_links(request):
    """Digital Asset Links: permite que el QR abra la app Android instalada."""
    path = _STATIC_PACIENTE / '.well-known' / 'assetlinks.json'
    return HttpResponse(
        path.read_text(encoding='utf-8'),
        content_type='application/json',
    )


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


@paciente_required
@require_POST
def push_subscribe(request):
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
            'cuidador': None,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
            'activo': True,
        },
    )
    return JsonResponse({'ok': True})


@paciente_required
@require_POST
def push_unsubscribe(request):
    data = _json_body(request) or {}
    endpoint = data.get('endpoint')
    if endpoint:
        SuscripcionPush.objects.filter(
            paciente=request.paciente,
            cuidador__isnull=True,
            endpoint=endpoint,
        ).update(activo=False)
    else:
        SuscripcionPush.objects.filter(
            paciente=request.paciente,
            cuidador__isnull=True,
        ).update(activo=False)
    return JsonResponse({'ok': True})


@paciente_required
@require_POST
def probar_notificacion(request):
    paciente = request.paciente
    canal = getattr(settings, 'NOTIFICACIONES_CANAL', 'sms')

    if canal == 'sms':
        if not (paciente.telefono or '').strip():
            messages.warning(
                request,
                'No hay teléfono registrado. Pida a su investigador que lo cargue en el panel.',
            )
            return redirect('paciente:perfil')
        if not labsmobile_configurado():
            messages.error(
                request,
                'El envío de SMS no está configurado en el servidor. Avise al administrador.',
            )
            return redirect('paciente:perfil')

        # Mensaje de prueba con el mismo formato compacto (sin tomas reales).
        from types import SimpleNamespace
        from django.utils import timezone as tz

        demo = SimpleNamespace(
            hora_programada=tz.localtime().time().replace(second=0, microsecond=0),
            medicamento=SimpleNamespace(nombre='Medicamento de prueba', dosis='1 dosis'),
        )
        resultado = enviar_sms_paciente(
            paciente,
            mensaje_recordatorio_grupo([demo], incluir_enlace=True),
        )
        if resultado.get('ok'):
            messages.success(
                request,
                f'SMS de prueba enviado a {resultado.get("msisdn")}. Revise su bandeja de mensajes.',
            )
        else:
            messages.error(
                request,
                f'No se pudo enviar el SMS ({resultado.get("error")}). '
                'Verifique el número o la configuración de LabsMobile.',
            )
        return redirect('paciente:perfil')

    tiene_suscripcion = paciente.push_subscriptions.filter(
        activo=True,
        cuidador__isnull=True,
    ).exists()
    if not tiene_suscripcion:
        messages.warning(
            request,
            'Primero active las alarmas en este celular (en Mis medicinas).',
        )
        return redirect('paciente:perfil')

    enviados = enviar_push_paciente(
        paciente,
        'Recordatin — Prueba',
        'Si ve este aviso, las notificaciones están bien configuradas.',
        url='/paciente/perfil/',
        tag='recordatin-prueba',
        demo=True,
    )
    if enviados:
        messages.success(request, 'Notificación de prueba enviada.')
    else:
        messages.error(request, 'No se pudo enviar la notificación.')
    return redirect('paciente:perfil')
