from django.contrib import admin

from .models import RemediationPlan, VerificationAttempt


class VerificationAttemptInline(admin.TabularInline):
    model = VerificationAttempt
    extra = 0
    readonly_fields = ("requested_at", "requested_by", "vulnerability_still_present", "scan_reference")


@admin.register(RemediationPlan)
class RemediationPlanAdmin(admin.ModelAdmin):
    list_display = ("vulnerability", "owner_name", "status", "due_date")
    list_filter = ("status",)
    inlines = [VerificationAttemptInline]
