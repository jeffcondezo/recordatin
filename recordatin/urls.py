from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from paciente.views import PacienteLoginView, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path(
        'accounts/login/',
        PacienteLoginView.as_view(),
        name='login',
    ),
    path('accounts/logout/', logout_view, name='logout'),
    path('paciente/', include('paciente.urls')),
]
