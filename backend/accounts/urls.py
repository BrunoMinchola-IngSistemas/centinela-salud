from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CambiarClaveView, MeView, MiembroViewSet, OrganizacionView

router = DefaultRouter()
router.register("usuarios", MiembroViewSet, basename="miembro")

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/cambiar-clave/", CambiarClaveView.as_view(), name="auth-cambiar-clave"),
    path("organizacion/", OrganizacionView.as_view(), name="organizacion"),
] + router.urls
