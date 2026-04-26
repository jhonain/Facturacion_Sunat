from django.urls import path
from .views import LibroVentasView, DashboardView

urlpatterns = [
    path('reportes/ventas-por-periodo/', LibroVentasView.as_view(), name='libro-ventas'),
    path('reportes/dashboard/',          DashboardView.as_view(),   name='dashboard'),
]
