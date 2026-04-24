from rest_framework import serializers
from .models import Empresa, SerieComprobante

class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = '__all__'

class SerieComprobanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SerieComprobante
        fields = '__all__'
