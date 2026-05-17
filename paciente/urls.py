from django.urls import path

from . import views

app_name = 'paciente'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('medicamentos/hoy/', views.medicamentos_hoy, name='medicamentos_hoy'),
    path('medicamentos/<int:toma_id>/tomar/', views.marcar_tomado, name='marcar_tomado'),
    path('historial/', views.historial, name='historial'),
    path('citas/', views.citas, name='citas'),
    path('perfil/', views.perfil, name='perfil'),
]
