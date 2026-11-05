from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth_views import LoginMFAView, LoginView, LogoutView, MFAView
from .views import CambiarClaveView, MeView, MiembroViewSet, OrganizacionView

router = DefaultRouter()
router.register("usuarios", MiembroViewSet, basename="miembro")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="api-login"),
    path("auth/login/mfa/", LoginMFAView.as_view(), name="api-login-mfa"),
    path("auth/logout/", LogoutView.as_view(), name="api-logout"),
    path("auth/mfa/", MFAView.as_view(), name="auth-mfa"),
    path("auth/mfa/<str:paso>/", MFAView.as_view(), name="auth-mfa-paso"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/cambiar-clave/", CambiarClaveView.as_view(), name="auth-cambiar-clave"),
    path("organizacion/", OrganizacionView.as_view(), name="organizacion"),
] + router.urls
