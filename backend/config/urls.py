"""
URL configuration for config project.

Toda la API vive bajo /api/. Cada app del dominio registra sus propias
rutas DRF (ver <app>/urls.py) y aquí solo se incluyen.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from .views import DashboardSummaryView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", obtain_auth_token, name="api-login"),
    path("api/dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("api/", include("accounts.urls")),
    path("api/", include("assets.urls")),
    path("api/", include("controls.urls")),
    path("api/", include("vulnerabilities.urls")),
    path("api/", include("remediation.urls")),
    path("api/", include("evidence.urls")),
]
