import io

import qrcode
from django.conf import settings
from django.urls import reverse


def url_acceso_paciente(paciente, request=None):
    path = reverse('paciente:entrar_qr', kwargs={'token': paciente.token_acceso})
    if request is not None:
        return request.build_absolute_uri(path)
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        return f'{site_url}{path}'
    return path


def url_acceso_cuidador(cuidador, request=None):
    path = reverse('paciente:cuidador_entrar', kwargs={'token': cuidador.token_acceso})
    if request is not None:
        return request.build_absolute_uri(path)
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        return f'{site_url}{path}'
    return path


def generar_imagen_qr(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()
