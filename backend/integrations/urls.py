from django.urls import path

from .views import EstadoIntegracionesView

urlpatterns = [
    path("integraciones/estado/", EstadoIntegracionesView.as_view(), name="integraciones-estado"),
]
