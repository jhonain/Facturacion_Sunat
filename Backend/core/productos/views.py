from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Producto, CategoriaProducto
from .serializer import ProductoSerializer, CategoriaProductoSerializer


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset           = CategoriaProducto.objects.select_related('empresa').all()
    serializer_class   = CategoriaProductoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields   = ['empresa', 'activa']
    ordering           = ['nombre']


class ProductoViewSet(viewsets.ModelViewSet):
    """
    CRUD de productos con búsqueda y filtros.

    Filtros disponibles:
        ?empresa=1
        ?activo=true
        ?tipo_afectacion_igv=10     → gravados
        ?search=laptop              → busca en código y descripción
    """
    queryset           = Producto.objects.select_related('empresa', 'categoria').all()
    serializer_class   = ProductoSerializer
    permission_classes = [IsAuthenticated]
    search_fields      = ['codigo', 'descripcion']
    filterset_fields   = ['empresa', 'activo', 'tipo_afectacion_igv', 'categoria']
    ordering_fields    = ['descripcion', 'precio_unitario', 'creado_en']
    ordering           = ['descripcion']
