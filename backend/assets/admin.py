from django.contrib import admin

from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("hostname", "asset_type", "criticality", "stores_phi", "wazuh_agent_online", "organization")
    list_filter = ("asset_type", "criticality", "stores_phi", "organization")
    search_fields = ("hostname", "ip_address")
