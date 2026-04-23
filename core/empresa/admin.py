from django.contrib import admin
from .models import Empresa, SerieComprobante

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display      = ['ruc', 'razon_social', 'nombre_comercial', 'regimen_tributario', 'activa']
    list_filter       = ['regimen_tributario', 'activa']
    search_fields     = ['ruc', 'razon_social', 'nombre_comercial', 'direccion']
    ordering          = ['razon_social']

@admin.register(SerieComprobante)
class SerieComprobanteAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'serie', 'tipo', 'correlativo_actual']
    list_filter  = ['tipo', 'empresa']
    search_fields = ['serie']
    ordering = ['empresa', 'serie']
