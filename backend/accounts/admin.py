from django.contrib import admin

from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "ruc", "created_at")
    search_fields = ("name", "ruc")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "mfa_enabled")
    list_filter = ("organization", "role")
