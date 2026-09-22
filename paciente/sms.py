"""Envío de SMS vía LabsMobile (JSON API)."""
from __future__ import annotations

import base64
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request

from django.conf import settings

from paciente.constants import SMS_MAX_CARACTERES

logger = logging.getLogger(__name__)

LABSMOBILE_SEND_URL = 'https://api.labsmobile.com/json/send'


def sms_texto_plano(texto: str) -> str:
    """
    Quita tildes/ñ y caracteres no GSM básicos para un SMS de 160 chars (7-bit).
    ñ→n, á→a, etc. Conserva saltos de línea y puntuación simple.
    """
    if not texto:
        return ''
    reemplazos = {
        'ñ': 'n', 'Ñ': 'N',
        'ü': 'u', 'Ü': 'U',
        '¿': '', '¡': '',
        '–': '-', '—': '-',
        '“': '"', '”': '"', '‘': "'", '’': "'",
        '…': '...',
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    nfkd = unicodedata.normalize('NFKD', texto)
    sin_marcas = ''.join(c for c in nfkd if not unicodedata.combining(c))
    limpio = ''.join(
        c for c in sin_marcas
        if c in '\n\r\t' or 32 <= ord(c) <= 126
    )
    limpio = re.sub(r'[ \t]+\n', '\n', limpio)
    limpio = re.sub(r'\n{3,}', '\n\n', limpio)
    return limpio.strip()


def normalizar_msisdn(telefono: str, pais_default: str | None = None) -> str | None:
    """
    Convierte un teléfono a MSISDN internacional (solo dígitos).
    Perú por defecto: 9 dígitos locales → prefijo 51.
    """
    if not telefono:
        return None
    digitos = re.sub(r'\D+', '', telefono.strip())
    if not digitos:
        return None
    if digitos.startswith('00'):
        digitos = digitos[2:]
    pais = pais_default or getattr(settings, 'LABSMOBILE_DEFAULT_COUNTRY', '51')
    if len(digitos) == 9 and pais == '51':
        digitos = f'{pais}{digitos}'
    elif len(digitos) < 10 and pais and not digitos.startswith(pais):
        digitos = f'{pais}{digitos}'
    if len(digitos) < 10:
        return None
    return digitos


def labsmobile_configurado() -> bool:
    return bool(
        getattr(settings, 'LABSMOBILE_USERNAME', '')
        and getattr(settings, 'LABSMOBILE_TOKEN', '')
    )


def enviar_sms(telefono: str, mensaje: str) -> dict:
    """
    Envía un SMS. Devuelve ok, msisdn, error, raw, chars.
    """
    mensaje = sms_texto_plano(mensaje)
    msisdn = normalizar_msisdn(telefono)
    if not msisdn:
        return {
            'ok': False, 'msisdn': None, 'error': 'telefono_invalido',
            'raw': None, 'chars': len(mensaje),
        }

    if not labsmobile_configurado():
        logger.warning('LabsMobile no configurado (LABSMOBILE_USERNAME / LABSMOBILE_TOKEN)')
        return {
            'ok': False, 'msisdn': msisdn, 'error': 'no_configurado',
            'raw': None, 'chars': len(mensaje),
        }

    username = settings.LABSMOBILE_USERNAME
    token = settings.LABSMOBILE_TOKEN
    sender = getattr(settings, 'LABSMOBILE_SENDER', '') or ''

    payload = {
        'message': mensaje[:SMS_MAX_CARACTERES],
        'recipient': [{'msisdn': msisdn}],
    }
    if sender:
        payload['tpoa'] = sms_texto_plano(sender)[:11]

    auth = base64.b64encode(f'{username}:{token}'.encode('utf-8')).decode('ascii')
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        LABSMOBILE_SEND_URL,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth}',
            'Accept': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_text = response.read().decode('utf-8', errors='replace')
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                raw = {'raw': raw_text}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='replace')
        logger.warning('LabsMobile HTTP %s: %s', exc.code, err_body[:300])
        return {
            'ok': False, 'msisdn': msisdn, 'error': f'http_{exc.code}',
            'raw': err_body, 'chars': len(mensaje),
        }
    except urllib.error.URLError as exc:
        logger.warning('LabsMobile red: %s', exc)
        return {
            'ok': False, 'msisdn': msisdn, 'error': 'red',
            'raw': str(exc), 'chars': len(mensaje),
        }

    code = str(raw.get('code', '')) if isinstance(raw, dict) else ''
    ok = code in ('0', '00', '')
    if isinstance(raw, dict) and 'code' in raw:
        ok = code in ('0', '00')
    if not ok and isinstance(raw, dict):
        msg = str(raw.get('message', '')).lower()
        if 'success' in msg or 'successfully' in msg:
            ok = True

    if not ok:
        logger.warning('LabsMobile respuesta no OK: %s', raw)

    return {
        'ok': ok,
        'msisdn': msisdn,
        'error': None if ok else str(
            raw.get('message', 'error') if isinstance(raw, dict) else 'error'
        ),
        'raw': raw,
        'chars': len(mensaje),
    }


def enviar_sms_paciente(paciente, mensaje: str) -> dict:
    return enviar_sms(paciente.telefono or '', mensaje)


def saludo_segun_hora(hora=None) -> str:
    """Buenos dias / Buenas tardes / Buenas noches segun la hora local (sin tildes)."""
    if hora is None:
        from django.utils import timezone
        hora = timezone.localtime().time()
    h = hora.hour
    if 5 <= h < 12:
        return 'Buenos dias'
    if 12 <= h < 19:
        return 'Buenas tardes'
    return 'Buenas noches'


def url_registro_app() -> str:
    """URL corta para el SMS (cabe mejor en 160 chars)."""
    site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if site:
        return f'{site}/paciente/'
    return 'https://spentor.app/paciente/'


def _linea_medicamento(toma) -> str:
    nombre = sms_texto_plano(toma.medicamento.nombre or '')
    dosis = sms_texto_plano((toma.medicamento.dosis or '').strip())
    if dosis:
        return f'- {nombre} {dosis}'
    return f'- {nombre}'


def mensaje_recordatorio_grupo(tomas, incluir_enlace=True) -> str:
    """
    Un SMS por paciente y horario, ASCII plano, max SMS_MAX_CARACTERES (160).
    """
    if not tomas:
        return ''
    tomas = sorted(tomas, key=lambda t: (t.medicamento.nombre or '').lower())
    hora = tomas[0].hora_programada.strftime('%H:%M')
    saludo = saludo_segun_hora()
    max_chars = SMS_MAX_CARACTERES

    cabecera = f'{saludo}. No olvide tomar a las {hora}:'
    if incluir_enlace:
        pie = f'Registrelo en la app: {url_registro_app()}'
    else:
        pie = 'Registrelo en la app Recordatin.'

    lineas_meds = [_linea_medicamento(t) for t in tomas]

    def armar(meds_lines):
        partes = [cabecera] + meds_lines + [pie]
        return sms_texto_plano('\n'.join(partes))

    mensaje = armar(lineas_meds)

    if len(mensaje) > max_chars and incluir_enlace:
        pie = 'Registrelo en la app Recordatin.'
        mensaje = armar(lineas_meds)

    while len(mensaje) > max_chars and len(lineas_meds) > 1:
        lineas_meds = lineas_meds[:-1]
        resto = len(tomas) - len(lineas_meds)
        meds_con_aviso = lineas_meds + [f'- y {resto} mas']
        mensaje = armar(meds_con_aviso)

    if len(mensaje) > max_chars:
        nombres = ', '.join(
            sms_texto_plano(t.medicamento.nombre or '') for t in tomas[:3]
        )
        if len(tomas) > 3:
            nombres += f' +{len(tomas) - 3}'
        mensaje = sms_texto_plano(
            f'{saludo}. A las {hora} tome: {nombres}. Registrelo en la app.'
        )
        if len(mensaje) > max_chars:
            mensaje = mensaje[: max_chars - 3].rstrip() + '...'

    return mensaje


def mensaje_alarma_toma(toma) -> str:
    """Compatibilidad: un solo medicamento."""
    return mensaje_recordatorio_grupo([toma])


def longitud_sms(mensaje: str) -> dict:
    """Utilidad para auditar tamano (GSM-7 aprox. si ya es texto plano)."""
    plano = sms_texto_plano(mensaje)
    n = len(plano)
    return {
        'chars': n,
        'max': SMS_MAX_CARACTERES,
        'cabe_en_uno': n <= SMS_MAX_CARACTERES,
        'mensaje': plano,
    }
