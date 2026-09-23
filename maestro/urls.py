from django.urls import path

from . import views

app_name = 'maestro'

urlpatterns = [
    path('login/', views.MaestroLoginView.as_view(), name='login'),
    path('logout/', views.logout_maestro, name='logout'),
    path('', views.panel, name='panel'),
    path('alarmas/', views.monitor_alarmas, name='monitor_alarmas'),
    path('pacientes/<int:paciente_id>/', views.paciente_detalle, name='paciente_detalle'),
    path('pacientes/<int:paciente_id>/qr.png', views.paciente_qr_png, name='paciente_qr_png'),
    path(
        'pacientes/<int:paciente_id>/medicamentos/nuevo/',
        views.medicamento_nuevo,
        name='medicamento_nuevo',
    ),
    path(
        'pacientes/<int:paciente_id>/medicamentos/<int:medicamento_id>/editar/',
        views.medicamento_editar,
        name='medicamento_editar',
    ),
    path(
        'pacientes/<int:paciente_id>/medicamentos/<int:medicamento_id>/desactivar/',
        views.medicamento_desactivar,
        name='medicamento_desactivar',
    ),
    path(
        'pacientes/<int:paciente_id>/consentimiento-firmado.pdf',
        views.paciente_consentimiento_firmado_pdf,
        name='paciente_consentimiento_firmado_pdf',
    ),
    path(
        'pacientes/<int:paciente_id>/anular-consentimiento/',
        views.paciente_anular_consentimiento,
        name='anular_consentimiento',
    ),
    path(
        'pacientes/<int:paciente_id>/recordar-seguimiento/',
        views.paciente_activar_seguimiento_hint,
        name='recordar_seguimiento',
    ),
    path(
        'pacientes/<int:paciente_id>/mmas8/<str:momento>/',
        views.paciente_mmas8,
        name='paciente_mmas8',
    ),
]
