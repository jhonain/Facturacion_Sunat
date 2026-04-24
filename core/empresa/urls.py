from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, SerieComprobanteViewSet

router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet)
router.register(r'series', SerieComprobanteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]