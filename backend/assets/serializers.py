from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    open_vulnerability_count = serializers.ReadOnlyField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "hostname",
            "asset_type",
            "ip_address",
            "operating_system",
            "criticality",
            "stores_phi",
            "wazuh_agent_id",
            "wazuh_agent_online",
            "tags",
            "first_seen",
            "last_seen",
            "open_vulnerability_count",
        ]
        read_only_fields = ["id", "first_seen", "last_seen"]
