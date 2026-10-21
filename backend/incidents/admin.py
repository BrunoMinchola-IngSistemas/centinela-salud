from django.contrib import admin

from .models import IncidenteReportado


@admin.register(IncidenteReportado)
class IncidenteReportadoAdmin(admin.ModelAdmin):
    list_display = ["lugar", "ocurrido_en", "estado", "organization", "reportado_por", "creado_en"]
    list_filter = ["estado", "organization"]
    search_fields = ["lugar", "descripcion"]
