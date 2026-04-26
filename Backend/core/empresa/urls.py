from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, SerieComprobanteViewSet

router = DefaultRouter()
router.register(r'empresa', EmpresaViewSet)
router.register(r'serie', SerieComprobanteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]