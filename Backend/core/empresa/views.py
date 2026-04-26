from rest_framework import viewsets
from .models import Empresa, SerieComprobante
from .serializer import EmpresaSerializer, SerieComprobanteSerializer

class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer

class SerieComprobanteViewSet(viewsets.ModelViewSet):
    queryset = SerieComprobante.objects.all()
    serializer_class = SerieComprobanteSerializer
