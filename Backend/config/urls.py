from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Apps
    path('api/v1/', include('core.empresa.urls')),
    path('api/v1/', include('core.productos.urls')),
    path('api/v1/', include('core.clientes.urls')),
    path('api/v1/', include('core.comprobantes.urls')),
    path('api/v1/', include('core.reportes.urls')),

    # JWT
    path('api/token/',         TokenObtainPairView.as_view(),  name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(),     name='token_refresh'),
]
