from django.conf import settings
from django.conf.urls.static import static
# -*- coding: utf-8 -*-
"""
Ruteo del arnes. NO viaja a sige-ube.

Reproduce el prefijo real del sistema para que las URLs con las que prueban
sean las mismas que van a existir en produccion:

    https://servidor/api/v1.0.0/movil/...
    https://servidor/api/v1.0.0/student/...
    https://servidor/api/v1.0.0/auth/...
    https://servidor/api/v1.0.0/period/...
"""
from django.contrib import admin
from django.urls import path, include

from app.auth_views import (
    SignInView,
    RefreshView,
    SignOutView,
    RecoverPasswordView,
    RecoverUsernameView,
    ChangePasswordView,
)
from app.period_views import PeriodListView, PeriodActiveView

auth_urlpatterns = [
    path('sign-in/', SignInView.as_view(), name='auth-sign-in'),
    path('refresh/', RefreshView.as_view(), name='auth-refresh'),
    path('sign-out/', SignOutView.as_view(), name='auth-sign-out'),
    path('recover-password/', RecoverPasswordView.as_view(), name='auth-recover-password'),
    path('recover-username/', RecoverUsernameView.as_view(), name='auth-recover-username'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
]

period_urlpatterns = [
    path('', PeriodListView.as_view(), name='period-list'),
    path('active/', PeriodActiveView.as_view(), name='period-active'),
]

from django.http import FileResponse, HttpResponse, JsonResponse

def docs_view(request):
    doc_file = settings.BASE_DIR / 'docs_completo.html'
    if doc_file.exists():
        return FileResponse(open(doc_file, 'rb'), content_type='text/html')
    return HttpResponse("SIGE-UBE API Móvil Online. Rutas disponibles en /api/v1.0.0/ y panel en /admin/.")

def api_root_view(request):
    return JsonResponse({
        "isSuccess": True,
        "message": "SIGE-UBE API Móvil v1.0.0 en línea",
        "version": "1.0.0",
        "docs": request.build_absolute_uri('/docs/'),
        "status": 200
    })

urlpatterns = [
    path('', docs_view, name='api-docs-home'),
    path('docs/', docs_view, name='api-docs'),
    path('admin/', admin.site.urls),
    path('api/v1.0.0/', api_root_view, name='api-root'),
    # Soporta tanto /movil/... como rutas directas sin prefijo movil
    path('api/v1.0.0/movil/', include('app.urls')),
    path('api/v1.0.0/', include('app.urls')),
    path('api/v1.0.0/auth/', include(auth_urlpatterns)),
    path('api/v1.0.0/period/', include(period_urlpatterns)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
