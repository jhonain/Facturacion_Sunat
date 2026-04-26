from rest_framework import serializers
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    tipo_documento_display = serializers.CharField(
        source='get_tipo_documento_display', read_only=True
    )

    class Meta:
        model  = Cliente
        fields = [
            'id', 'empresa',
            'tipo_documento', 'tipo_documento_display',
            'numero_documento', 'razon_social',
            'direccion', 'correo', 'telefono',
            'activo', 'creado_en',
        ]
        read_only_fields = ['creado_en']

    def validate(self, data):
        tipo = data.get('tipo_documento', getattr(self.instance, 'tipo_documento', None))
        num  = data.get('numero_documento', getattr(self.instance, 'numero_documento', ''))

        if tipo == Cliente.TipoDocumento.RUC:
            if not num.isdigit() or len(num) != 11:
                raise serializers.ValidationError(
                    {'numero_documento': 'El RUC debe tener exactamente 11 dígitos numéricos.'}
                )

        elif tipo == Cliente.TipoDocumento.DNI:
            if not num.isdigit() or len(num) != 8:
                raise serializers.ValidationError(
                    {'numero_documento': 'El DNI debe tener exactamente 8 dígitos numéricos.'}
                )

        return data
