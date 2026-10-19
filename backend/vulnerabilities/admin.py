from django.contrib import admin

from .models import Vulnerability, VulnerabilitySource


@admin.register(VulnerabilitySource)
class VulnerabilitySourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "organization", "is_active", "last_sync_ok", "last_sync_at")
    list_filter = ("source_type", "is_active", "organization")


@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ("cve", "title", "asset", "severity", "priority_score", "status", "due_date")
    list_filter = ("severity", "status", "source__source_type", "organization")
    search_fields = ("cve", "title", "asset__hostname")
    autocomplete_fields = ("asset",)
