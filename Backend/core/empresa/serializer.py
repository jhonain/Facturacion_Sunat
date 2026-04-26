from rest_framework import serializers
from .models import Empresa, SerieComprobante


class EmpresaSerializer(serializers.ModelSerializer):
    regimen_display = serializers.CharField(
        source='get_regimen_tributario_display', read_only=True
    )

    class Meta:
        model  = Empresa
        fields = [
            'id', 'ruc', 'razon_social', 'nombre_comercial',
            'direccion', 'regimen_tributario', 'regimen_display',
            'activa', 'creado_en',
        ]
        read_only_fields = ['creado_en']

    def validate_ruc(self, value):
        if not value.isdigit() or len(value) != 11:
            raise serializers.ValidationError(
                'El RUC de la empresa debe tener exactamente 11 dígitos numéricos.'
            )
        return value


class SerieComprobanteSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(
        source='get_tipo_display', read_only=True
    )

    class Meta:
        model  = SerieComprobante
        fields = [
            'id', 'empresa', 'tipo', 'tipo_display',
            'serie', 'correlativo_actual',
        ]
        read_only_fields = ['correlativo_actual']

    def validate_serie(self, value):
        value = value.strip().upper()
        if len(value) != 4:
            raise serializers.ValidationError(
                'La serie debe tener exactamente 4 caracteres (ej: F001, B001).'
            )
        return value
