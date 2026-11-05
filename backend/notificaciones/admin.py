from django.contrib import admin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ["titulo", "destinatario", "tipo", "nivel", "leida", "creada_en"]
    list_filter = ["tipo", "nivel", "leida"]
