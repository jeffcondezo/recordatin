import base64

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from paciente.qr import generar_imagen_qr, url_acceso_paciente

from .models import (
    CitaMedica,
    Cuidador,
    EvaluacionMMAS8,
    HorarioToma,
    MedicamentoPrescrito,
    Paciente,
    Prescripcion,
    RegistroRecompensaDiaria,
    SuscripcionPush,
    TomaMedicamento,
)


class CuidadorInline(admin.TabularInline):
    model = Cuidador
    extra = 0
    readonly_fields = ('token_acceso', 'vinculado_en', 'ultimo_acceso')
    fields = ('nombre', 'activo', 'token_acceso', 'vinculado_en', 'ultimo_acceso')


class HorarioTomaInline(admin.TabularInline):
    model = HorarioToma
    extra = 1


class MedicamentoPrescritoInline(admin.TabularInline):
    model = MedicamentoPrescrito
    extra = 0
    show_change_link = True


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_estudio', 'nombre', 'grupo',
        'dias_cumplidos', 'user', 'activo', 'tiene_token_qr',
    )
    list_filter = ('grupo', 'activo', 'sexo')
    search_fields = ('nombre', 'apellidos', 'codigo_estudio', 'dni', 'user__username')
    readonly_fields = (
        'token_acceso', 'enlace_acceso', 'qr_preview', 'descargar_qr',
        'primer_acceso', 'consentimiento_aceptado_at', 'consentimiento_firma',
    )
    actions = ['regenerar_codigo_qr']
    inlines = [CuidadorInline]

    fieldsets = (
        (None, {
            'fields': (
                'user', 'codigo_estudio', 'nombre', 'dni', 'telefono',
                'fecha_nacimiento', 'edad', 'sexo', 'activo', 'dias_cumplidos',
            ),
        }),
        ('Estudio', {
            'fields': ('grupo', 'fecha_ingreso_estudio', 'primer_acceso', 'consentimiento_aceptado_at', 'consentimiento_firma'),
        }),
        ('Acceso por QR', {
            'fields': ('token_acceso', 'enlace_acceso', 'qr_preview', 'descargar_qr'),
            'description': (
                'El código QR es como una llave de acceso. Imprímalo y entréguelo al paciente. '
                'Si se pierde o filtra, use la acción «Regenerar código QR» para invalidar el anterior.'
            ),
        }),
        ('Clínico', {
            'fields': ('diagnostico_principal', 'enfermedad_2', 'enfermedad_3'),
        }),
    )

    @admin.display(boolean=True, description='QR')
    def tiene_token_qr(self, obj):
        return bool(obj.token_acceso)

    @admin.display(description='Enlace de acceso')
    def enlace_acceso(self, obj):
        if not obj.pk or not obj.token_acceso:
            return '—'
        url = url_acceso_paciente(obj)
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

    @admin.display(description='Vista previa QR')
    def qr_preview(self, obj):
        if not obj.pk or not obj.token_acceso:
            return '—'
        url = url_acceso_paciente(obj)
        png = base64.b64encode(generar_imagen_qr(url)).decode('ascii')
        return format_html(
            '<img src="data:image/png;base64,{}" alt="QR de acceso" style="max-width:220px;height:auto;">',
            png,
        )

    @admin.display(description='Descargar')
    def descargar_qr(self, obj):
        if not obj.pk or not obj.token_acceso:
            return '—'
        url = reverse('admin:core_paciente_qr_png', args=[obj.pk])
        return format_html('<a class="button" href="{}">Descargar QR (PNG)</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:paciente_id>/qr.png/',
                self.admin_site.admin_view(self.descargar_qr_png),
                name='core_paciente_qr_png',
            ),
        ]
        return custom + urls

    def descargar_qr_png(self, request, paciente_id):
        paciente = Paciente.objects.get(pk=paciente_id)
        url = url_acceso_paciente(paciente, request=request)
        png = generar_imagen_qr(url)
        response = HttpResponse(png, content_type='image/png')
        filename = f'recordatin-qr-{paciente.pk}.png'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @admin.action(description='Regenerar código QR')
    def regenerar_codigo_qr(self, request, queryset):
        for paciente in queryset:
            paciente.regenerar_token_acceso()
        self.message_user(request, f'Se regeneró el código QR de {queryset.count()} paciente(s).')


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
    list_display = (
        'paciente', 'medicamento', 'fecha', 'hora_programada',
        'estado', 'a_tiempo', 'alarma_enviada_at',
    )
    list_filter = ('estado', 'fecha')


@admin.register(RegistroRecompensaDiaria)
class RegistroRecompensaDiariaAdmin(admin.ModelAdmin):
    list_display = (
        'paciente', 'fecha', 'resultado',
        'dias_antes', 'dias_despues', 'procesado_en',
    )
    list_filter = ('resultado', 'fecha')


@admin.register(EvaluacionMMAS8)
class EvaluacionMMAS8Admin(admin.ModelAdmin):
    list_display = (
        'paciente', 'momento', 'puntaje', 'categoria',
        'registrado_por', 'fecha',
    )
    list_filter = ('momento', 'categoria', 'registrado_por')
    search_fields = ('paciente__nombre', 'paciente__codigo_estudio')


@admin.register(SuscripcionPush)
class SuscripcionPushAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'cuidador', 'activo', 'creado_en', 'endpoint')
    list_filter = ('activo',)
    search_fields = ('paciente__nombre', 'endpoint')


@admin.register(Cuidador)
class CuidadorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'paciente', 'activo', 'vinculado_en', 'ultimo_acceso')
    list_filter = ('activo',)
    search_fields = ('nombre', 'paciente__nombre', 'token_acceso')
    readonly_fields = ('token_acceso', 'vinculado_en', 'ultimo_acceso')
    actions = ['revocar_cuidadores']

    @admin.action(description='Revocar acceso (desactivar)')
    def revocar_cuidadores(self, request, queryset):
        ids = list(queryset.values_list('pk', flat=True))
        count = queryset.update(activo=False)
        SuscripcionPush.objects.filter(cuidador_id__in=ids).update(activo=False)
        self.message_user(request, f'Se revocó el acceso de {count} cuidador(es).')


@admin.register(CitaMedica)
class CitaMedicaAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha_hora', 'especialidad', 'estado')
    list_filter = ('estado',)
