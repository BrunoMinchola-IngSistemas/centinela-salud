"""
HU30: "Permitir que el personal reporte un incidente de seguridad con
máximo 3 campos (qué pasó, dónde, cuándo)". A propósito NO se modela
como un formulario largo: la idea es que cualquier persona del personal
clínico, sin entrenamiento técnico, pueda reportar algo sospechoso en
segundos.
"""

import uuid

from django.db import models

from accounts.models import Organization


class EstadoIncidente(models.TextChoices):
    REPORTADO = "reportado", "Reportado"
    EN_REVISION = "en_revision", "En revisión"
    CERRADO = "cerrado", "Cerrado"


class IncidenteReportado(models.Model):
    """
    Los 3 campos de HU30: qué pasó (`descripcion`), dónde (`lugar`) y
    cuándo (`ocurrido_en`). Todo lo demás (quién reportó, el estado, la
    organización) se completa solo, no son parte de "los 3 campos" que
    la persona tiene que llenar.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="incidentes")
    reportado_por = models.CharField(max_length=150, blank=True, help_text="Usuario que reportó, si inició sesión.")

    # Los 3 campos que sí llena la persona:
    descripcion = models.TextField(help_text="Qué pasó.")
    lugar = models.CharField(max_length=150, help_text="Dónde pasó (área, equipo, sistema).")
    ocurrido_en = models.DateTimeField(help_text="Cuándo pasó.")

    estado = models.CharField(max_length=20, choices=EstadoIncidente.choices, default=EstadoIncidente.REPORTADO)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Incidente reportado"
        verbose_name_plural = "Incidentes reportados"

    def __str__(self):
        return f"{self.lugar} · {self.ocurrido_en:%Y-%m-%d} · {self.get_estado_display()}"
