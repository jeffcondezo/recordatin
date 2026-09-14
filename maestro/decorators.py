from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def maestro_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('maestro:login')
        if not request.user.is_staff:
            messages.error(
                request,
                'No tiene permiso para acceder al panel del estudio.',
            )
            return redirect('maestro:login')
        return view_func(request, *args, **kwargs)

    return wrapper
