from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ComprobanteViewSet, FacturaViewSet, BoletaViewSet, NotaCreditoViewSet

router = DefaultRouter()
router.register(r'comprobantes',  ComprobanteViewSet)
router.register(r'facturas',      FacturaViewSet, basename='factura')
router.register(r'boletas',       BoletaViewSet, basename='boleta')
router.register(r'notas-credito', NotaCreditoViewSet, basename='nota-credito')

urlpatterns = [
    path('', include(router.urls)),
]
