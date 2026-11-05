"""
HU02 / HU04: trazas de la recolección automática de datos.

- FallaIntegracion: "log de fallas" cuando una fuente no responde; la
  recolección sigue con las demás fuentes.
- RegistroIncompleto: un registro que llegó sin algún campo obligatorio
  del esquema único. Se excluye del análisis (no se crea el hallazgo)
  hasta que alguien lo corrija.
"""

import uuid

from django.db import models

from accounts.models import Organization


class FallaIntegracion(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="fallas_integracion")
    fuente = models.ForeignKey(
        "vulnerabilities.VulnerabilitySource", on_delete=models.SET_NULL, null=True, blank=True, related_name="fallas"
    )
    fuente_nombre = models.CharField(max_length=100)
    error = models.TextField()
    ocurrido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ocurrido_en"]


class RegistroIncompleto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="registros_incompletos")
    fuente = models.ForeignKey(
        "vulnerabilities.VulnerabilitySource", on_delete=models.CASCADE, related_name="registros_incompletos"
    )
    external_id = models.CharField(max_length=100, blank=True)
    datos = models.JSONField(default=dict, help_text="Registro ya normalizado (y seudonimizado) tal como llegó.")
    campos_faltantes = models.JSONField(default=list)
    recibido_en = models.DateTimeField(auto_now_add=True)
    corregido = models.BooleanField(default=False)
    corregido_por = models.CharField(max_length=150, blank=True)
    corregido_en = models.DateTimeField(null=True, blank=True)
    vulnerabilidad = models.ForeignKey(
        "vulnerabilities.Vulnerability", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["corregido", "-recibido_en"]
