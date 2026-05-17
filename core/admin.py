from django.contrib import admin

from .models import (
    CitaMedica,
    HorarioToma,
    MedicamentoPrescrito,
    Paciente,
    Prescripcion,
    TomaMedicamento,
)


class HorarioTomaInline(admin.TabularInline):
    model = HorarioToma
    extra = 1


class MedicamentoPrescritoInline(admin.TabularInline):
    model = MedicamentoPrescrito
    extra = 0
    show_change_link = True


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellidos', 'user', 'activo')
    search_fields = ('nombre', 'apellidos', 'user__username')


@admin.register(Prescripcion)
class PrescripcionAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha_emision', 'medico_nombre', 'activa')
    list_filter = ('activa',)
    inlines = [MedicamentoPrescritoInline]


@admin.register(MedicamentoPrescrito)
class MedicamentoPrescritoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dosis', 'prescripcion', 'activo')
    inlines = [HorarioTomaInline]


@admin.register(TomaMedicamento)
class TomaMedicamentoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'medicamento', 'fecha', 'hora_programada', 'estado')
    list_filter = ('estado', 'fecha')


@admin.register(CitaMedica)
class CitaMedicaAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha_hora', 'especialidad', 'estado')
    list_filter = ('estado',)
