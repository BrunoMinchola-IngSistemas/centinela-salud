"""
URL configuration for config project.

Toda la API vive bajo /api/. Cada app del dominio registra sus propias
rutas DRF (ver <app>/urls.py) y aquí solo se incluyen.
"""

from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from .views import DashboardSummaryView


def salud(request):
    """Chequeo de salud para Docker/Caddy: responde 200 si la API y la base responden."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return JsonResponse({"ok": True})
    except Exception:  # noqa: BLE001
        return JsonResponse({"ok": False}, status=503)


urlpatterns = [
    path("api/salud/", salud, name="salud"),
    path("api/dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("api/", include("accounts.urls")),
    path("api/", include("assets.urls")),
    path("api/", include("controls.urls")),
    path("api/", include("vulnerabilities.urls")),
    path("api/", include("remediation.urls")),
    path("api/", include("evidence.urls")),
    path("api/", include("governance.urls")),
    path("api/", include("incidents.urls")),
    path("api/", include("integrations.urls")),
    path("api/", include("notificaciones.urls")),
    path("api/", include("informes.urls")),
]

# El admin de Django solo se publica si está habilitado (en la nube va
# apagado: su login no pasa por el bloqueo de intentos ni el MFA).
if settings.ADMIN_DJANGO_HABILITADO:
    urlpatterns.insert(0, path(settings.ADMIN_URL, admin.site.urls))
