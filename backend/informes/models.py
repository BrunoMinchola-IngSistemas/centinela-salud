"""
HU20/HU21 (y OE3): foto diaria del nivel de riesgo y reportes generados.

SnapshotRiesgo guarda una vez al día el Risk Score y el % de
cumplimiento. La primera foto es la "línea base": la tesis (OE3) pide
medir la variación del nivel de exposición al riesgo respecto de ella.
"""

import uuid

from django.db import models

from accounts.models import Organization


class SnapshotRiesgo(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="snapshots_riesgo")
    fecha = models.DateField()
    risk_score = models.PositiveSmallIntegerField()
    exposicion = models.PositiveSmallIntegerField(default=0)
    cumplimiento_global = models.PositiveSmallIntegerField()
    abiertas = models.PositiveIntegerField(default=0)
    criticas = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha"]
        constraints = [models.UniqueConstraint(fields=["organization", "fecha"], name="uniq_snapshot_por_dia")]


def _ruta_reporte(instance, filename):
    return f"reportes/{instance.organization_id}/{filename}"


class FormatoReporte(models.TextChoices):
    PDF = "pdf", "PDF"
    XLSX = "xlsx", "Excel"


class ReporteGenerado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reportes")
    formato = models.CharField(max_length=5, choices=FormatoReporte.choices)
    periodo_desde = models.DateField()
    periodo_hasta = models.DateField()
    archivo = models.FileField(upload_to=_ruta_reporte, max_length=300)
    sha256_hash = models.CharField(max_length=64)
    automatico = models.BooleanField(default=False, help_text="Generado por la periodicidad configurada (HU21).")
    generado_por = models.CharField(max_length=150)
    generado_en = models.DateTimeField(auto_now_add=True)
    resumen = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-generado_en"]
