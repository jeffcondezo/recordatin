from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect, render

from .cuidador_auth import obtener_cuidador_sesion
from .services import obtener_paciente


def paciente_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('entrada')

        paciente = obtener_paciente(request.user)
        if paciente is None:
            messages.error(
                request,
                'Tu cuenta no está vinculada a un perfil de paciente.',
            )
            return redirect('entrada')

        if not paciente.activo:
            messages.error(request, 'Tu perfil de paciente está inactivo.')
            return redirect('entrada')

        request.paciente = paciente
        return view_func(request, *args, **kwargs)

    return wrapper


def cuidador_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        cuidador = obtener_cuidador_sesion(request.session)
        if cuidador is None:
            return render(
                request,
                'paciente/cuidador/entrada_error.html',
                status=403,
            )

        if not cuidador.paciente.activo:
            messages.error(request, 'El perfil del paciente ya no está activo.')
            return render(
                request,
                'paciente/cuidador/entrada_error.html',
                status=403,
            )

        request.cuidador = cuidador
        request.paciente = cuidador.paciente
        return view_func(request, *args, **kwargs)

    return wrapper
