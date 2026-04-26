from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Cliente
from .serializer import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    """
    CRUD de clientes con búsqueda y filtros.

    Filtros disponibles:
        ?empresa=1
        ?tipo_documento=6       → solo RUC
        ?search=20601234567     → busca por número de documento o razón social
        ?activo=true
    """
    queryset           = Cliente.objects.select_related('empresa').all()
    serializer_class   = ClienteSerializer
    permission_classes = [IsAuthenticated]
    search_fields      = ['numero_documento', 'razon_social']
    filterset_fields   = ['empresa', 'tipo_documento', 'activo']
    ordering_fields    = ['razon_social', 'creado_en']
    ordering           = ['razon_social']
