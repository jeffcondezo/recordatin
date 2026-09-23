from django.urls import path

from . import views
from . import views_cuidador

app_name = 'paciente'

urlpatterns = [
    path('', views.paciente_home, name='home'),
    path('consentimiento/', views.consentimiento, name='consentimiento'),
    path('consentimiento/documento.pdf', views.consentimiento_pdf, name='consentimiento_pdf'),
    path(
        'consentimiento/firmado.pdf',
        views.consentimiento_firmado_pdf,
        name='consentimiento_firmado_pdf',
    ),
    path('entrar/<str:token>/', views.entrar_por_qr, name='entrar_qr'),
    path('medicamentos/hoy/', views.medicamentos_hoy, name='medicamentos_hoy'),
    path('medicamentos/<int:toma_id>/tomar/', views.marcar_tomado, name='marcar_tomado'),
    path('medicamentos/<int:toma_id>/tomar-api/', views.marcar_tomado_api, name='marcar_tomado_api'),
    path('medicamentos/<int:toma_id>/tomar-notif/', views.marcar_tomado_desde_notif, name='marcar_tomado_notif'),
    path('tratamiento/', views.tratamiento, name='tratamiento'),
    path('resumen/', views.dashboard, name='dashboard'),
    path('historial/', views.historial, name='historial'),
    path('citas/', views.citas, name='citas'),
    path('perfil/', views.perfil, name='perfil'),
    path('dias-cumplidos/', views.dias_cumplidos, name='dias_cumplidos'),
    path('mmas8/', views.mmas8_inicio, name='mmas8_inicio'),
    path('mmas8/<str:momento>/', views.mmas8_formulario, name='mmas8'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.webmanifest', views.web_manifest, name='web_manifest'),
    path('api/push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('api/push/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
    path('api/push/probar/', views.probar_notificacion, name='probar_notificacion'),
    path('cuidador/entrar/<str:token>/', views_cuidador.entrar_cuidador_por_qr, name='cuidador_entrar'),
    path('cuidador/', views_cuidador.cuidador_panel, name='cuidador_panel'),
    path('cuidador/citas/', views_cuidador.cuidador_citas, name='cuidador_citas'),
    path('cuidador/citas/nueva/', views_cuidador.cuidador_cita_nueva, name='cuidador_cita_nueva'),
    path('cuidador/citas/<int:cita_id>/editar/', views_cuidador.cuidador_cita_editar, name='cuidador_cita_editar'),
    path('cuidador/citas/<int:cita_id>/cancelar/', views_cuidador.cuidador_cita_cancelar, name='cuidador_cita_cancelar'),
    path('cuidador/salir/', views_cuidador.cuidador_salir, name='cuidador_salir'),
    path('api/cuidador/push/subscribe/', views_cuidador.cuidador_push_subscribe, name='cuidador_push_subscribe'),
    path('api/cuidador/push/unsubscribe/', views_cuidador.cuidador_push_unsubscribe, name='cuidador_push_unsubscribe'),
]
