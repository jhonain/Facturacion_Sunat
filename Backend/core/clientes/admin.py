from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display    = ['numero_documento', 'razon_social', 'empresa',
                       'tipo_documento', 'correo', 'telefono', 'activo']
    list_filter     = ['tipo_documento', 'activo', 'empresa']
    search_fields   = ['numero_documento', 'razon_social', 'correo', 'telefono']
    ordering        = ['razon_social']
    readonly_fields = ['creado_en']
