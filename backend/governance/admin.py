from django.contrib import admin

from .models import PoliticaAutonomia, RegistroAuditoria, SolicitudAprobacion


@admin.register(PoliticaAutonomia)
class PoliticaAutonomiaAdmin(admin.ModelAdmin):
    list_display = ["organization", "tipo_accion", "nivel", "actualizado_en"]
    list_filter = ["nivel", "organization"]


@admin.register(SolicitudAprobacion)
class SolicitudAprobacionAdmin(admin.ModelAdmin):
    list_display = ["id", "plan", "tipo_accion", "estado", "solicitado_en", "plazo"]
    list_filter = ["estado", "tipo_accion"]


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["creado_en", "organization", "actor", "accion", "modalidad", "objeto_tipo"]
    list_filter = ["modalidad", "organization", "objeto_tipo"]
    search_fields = ["actor", "accion", "objeto_id"]

    def has_change_permission(self, request, obj=None):
        # Refuerza en el admin la misma regla del modelo: el registro de
        # auditoría es de solo inserción (HU27 / RNF-05).
        return False

    def has_delete_permission(self, request, obj=None):
        return False
