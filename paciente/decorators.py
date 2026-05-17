from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from .services import obtener_paciente


def paciente_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        paciente = obtener_paciente(request.user)
        if paciente is None:
            messages.error(
                request,
                'Tu cuenta no está vinculada a un perfil de paciente.',
            )
            return redirect('login')

        if not paciente.activo:
            messages.error(request, 'Tu perfil de paciente está inactivo.')
            return redirect('login')

        request.paciente = paciente
        return view_func(request, *args, **kwargs)

    return wrapper
