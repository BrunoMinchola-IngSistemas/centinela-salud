from django.contrib import admin

from .models import Evidence


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("name", "evidence_type", "vulnerability", "source_system", "created_at")
    list_filter = ("evidence_type", "source_system")
    search_fields = ("name", "sha256_hash")
