from django.contrib import admin
from .models import CategoriaProducto, Producto
# Register your models here.
@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'descripcion']
    search_fields = ['nombre']
    ordering      = ['nombre']


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display   = ['codigo', 'descripcion', 'empresa', 'categoria', 
                      'unidad_medida', 'precio_unitario', 
                      'tipo_afectacion_igv', 'activo']
    list_filter    = ['tipo_afectacion_igv', 'activo', 'empresa', 'categoria']
    search_fields  = ['codigo', 'descripcion']
    ordering       = ['descripcion']
    readonly_fields = ['creado_en']