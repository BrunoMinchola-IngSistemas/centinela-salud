from django.contrib import admin

from .models import ComplianceAssessment, Control, ControlMapping


class ControlMappingInline(admin.TabularInline):
    model = ControlMapping
    extra = 1


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "baseline_score")
    inlines = [ControlMappingInline]
    search_fields = ("name",)


@admin.register(ComplianceAssessment)
class ComplianceAssessmentAdmin(admin.ModelAdmin):
    list_display = ("control", "score", "generated_by_ai", "created_at")
    list_filter = ("generated_by_ai",)
