from django.contrib import admin

from .models import ReporteGenerado, SnapshotRiesgo


@admin.register(SnapshotRiesgo)
class SnapshotRiesgoAdmin(admin.ModelAdmin):
    list_display = ["organization", "fecha", "risk_score", "cumplimiento_global", "abiertas"]


@admin.register(ReporteGenerado)
class ReporteGeneradoAdmin(admin.ModelAdmin):
    list_display = ["organization", "formato", "periodo_desde", "periodo_hasta", "automatico", "generado_en"]
