from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from paciente.views import PacienteLoginView, android_asset_links, entrada, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        '.well-known/assetlinks.json',
        android_asset_links,
        name='android_asset_links',
    ),
    path('', entrada, name='entrada'),
    path(
        'accounts/login/',
        PacienteLoginView.as_view(),
        name='login',
    ),
    path('accounts/logout/', logout_view, name='logout'),
    path('paciente/', include('paciente.urls')),
    path('maestro/', include('maestro.urls')),
]

# Firmas de consentimiento y demás archivos subidos
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
