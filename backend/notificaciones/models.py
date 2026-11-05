"""
Notificaciones del agente a las personas (HU05, HU22, HU24, HU30, HU03).

Una fila por destinatario, para que cada uno marque como leída la suya.
La consola las consulta cada pocos segundos (campana de la barra
superior), así que llegan "en tiempo real" sin depender del correo; si
la persona tiene correo y hay servidor SMTP (Amazon SES en AWS), además
se envía un email.
"""

import uuid

from django.conf import settings
from django.db import models

from accounts.models import Organization


class NivelNotificacion(models.TextChoices):
    INFO = "info", "Informativa"
    ADVERTENCIA = "advertencia", "Advertencia"
    CRITICA = "critica", "Crítica"


class TipoNotificacion(models.TextChoices):
    ACTIVO_NUEVO = "activo_nuevo", "Activo nuevo detectado"
    VENCIMIENTO = "vencimiento", "Hallazgo vencido"
    APROBACION = "aprobacion", "Solicitud de aprobación"
    ESCALAMIENTO = "escalamiento", "Solicitud escalada"
    INCIDENTE = "incidente", "Incidente reportado"
    CVE = "cve", "Base de conocimiento CVE"
    ACCION_AGENTE = "accion_agente", "Acción del agente"
    REPORTE = "reporte", "Reporte generado"
    SEGURIDAD = "seguridad", "Seguridad de la cuenta"
    INTEGRACION = "integracion", "Integración"


class Notificacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="notificaciones")
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones")
    tipo = models.CharField(max_length=20, choices=TipoNotificacion.choices)
    nivel = models.CharField(max_length=12, choices=NivelNotificacion.choices, default=NivelNotificacion.INFO)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True)
    enlace = models.CharField(max_length=200, blank=True, help_text="Ruta de la consola, p. ej. /activos.")
    objeto_tipo = models.CharField(max_length=50, blank=True)
    objeto_id = models.CharField(max_length=64, blank=True)
    leida = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    email_enviado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-creada_en"]
        indexes = [models.Index(fields=["destinatario", "leida"])]

    def __str__(self):
        return f"{self.titulo} → {self.destinatario}"
