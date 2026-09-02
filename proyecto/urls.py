# -*- coding: utf-8 -*-
"""
Ruteo del arnes. NO viaja a sige-ube.

Reproduce el prefijo real del sistema para que las URLs con las que prueban
sean las mismas que van a existir en produccion:

    https://servidor/api/v1.0.0/movil/...
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1.0.0/movil/', include('app.urls')),
]
