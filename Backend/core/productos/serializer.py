from rest_framework import serializers
from .models import CategoriaProducto, Producto


class CategoriaProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CategoriaProducto
        fields = ['id', 'empresa', 'nombre', 'descripcion', 'activa']


class ProductoSerializer(serializers.ModelSerializer):
    tipo_afectacion_display = serializers.CharField(
        source='get_tipo_afectacion_igv_display', read_only=True
    )
    precio_con_igv = serializers.SerializerMethodField()
    categoria_nombre = serializers.CharField(
        source='categoria.nombre', read_only=True
    )

    class Meta:
        model  = Producto
        fields = [
            'id', 'empresa', 'categoria', 'categoria_nombre',
            'codigo', 'descripcion', 'unidad_medida',
            'precio_unitario', 'precio_con_igv',
            'tipo_afectacion_igv', 'tipo_afectacion_display',
            'activo', 'creado_en',
        ]
        read_only_fields = ['creado_en']

    def get_precio_con_igv(self, obj):
        return round(obj.precio_con_igv(), 4)

    def validate_precio_unitario(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'El precio unitario debe ser mayor a 0.'
            )
        return value

    def validate_codigo(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                'El código del producto no puede estar vacío.'
            )
        return value.strip().upper()
