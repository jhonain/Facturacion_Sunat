from django.contrib import admin
from .models import Comprobante, DetalleComprobante, LogEnvioSunat, NotaCredito


class DetalleComprobanteInline(admin.TabularInline):
    model           = DetalleComprobante
    extra           = 0
    readonly_fields = ['igv_linea', 'subtotal', 'total']
    fields          = [
        'producto', 'descripcion', 'cantidad',
        'unidad_medida', 'precio_unitario', 'descuento',
        'igv_linea', 'subtotal', 'total'
    ]


class LogEnvioSunatInline(admin.TabularInline):
    model           = LogEnvioSunat
    extra           = 0
    readonly_fields = ['fecha_envio', 'estado_respuesta',
                       'codigo_respuesta', 'descripcion']
    can_delete      = False


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'empresa', 'tipo', 'fecha_emision',
                       'moneda', 'subtotal', 'igv', 'total', 'estado']
    list_filter     = ['tipo', 'estado', 'moneda', 'empresa', 'fecha_emision']
    search_fields   = ['numero', 'cliente__razon_social',
                       'cliente__numero_documento', 'serie__serie']
    ordering        = ['-fecha_emision', '-numero']
    readonly_fields = ['creado_en', 'actualizado_en',
                       'sunat_ticket', 'sunat_cdr', 'sunat_descripcion']
    inlines         = [DetalleComprobanteInline, LogEnvioSunatInline]

    fieldsets = (
        ('Información Principal', {
            'fields': (
                'empresa', 'serie', 'cliente',
                'tipo', 'numero', 'fecha_emision',
                'moneda', 'estado'
            )
        }),
        ('Totales', {
            'fields': ('subtotal', 'igv', 'total')
        }),
        ('SUNAT', {
            'fields': (
                'xml_firmado', 'sunat_ticket',
                'sunat_cdr', 'sunat_descripcion'
            ),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LogEnvioSunat)
class LogEnvioSunatAdmin(admin.ModelAdmin):
    list_display    = ['comprobante', 'fecha_envio', 'estado_respuesta',
                       'codigo_respuesta', 'descripcion']
    list_filter     = ['estado_respuesta', 'fecha_envio']
    search_fields   = ['comprobante__serie__serie', 'descripcion']
    ordering        = ['-fecha_envio']
    readonly_fields = ['fecha_envio']


@admin.register(NotaCredito)
class NotaCreditoAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'tipo_nota', 'monto_afectado', 'motivo']
    list_filter     = ['tipo_nota']
    search_fields   = ['motivo', 'comprobante_referencia__serie__serie']
    ordering        = ['comprobante_referencia']
    readonly_fields = ['comprobante_nota']