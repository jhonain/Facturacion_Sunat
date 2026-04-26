from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductoViewSet, CategoriaProductoViewSet

router = DefaultRouter()
router.register(r'producto', ProductoViewSet)
router.register(r'categoria', CategoriaProductoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]