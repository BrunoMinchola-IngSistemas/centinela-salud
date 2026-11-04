from rest_framework import serializers

from .models import Asset, DiscoveryRun, DiscoverySource


class AssetSerializer(serializers.ModelSerializer):
    open_vulnerability_count = serializers.ReadOnlyField()
    estado = serializers.ReadOnlyField()
    asset_type_display = serializers.CharField(source="get_asset_type_display", read_only=True)
    discovery_source_display = serializers.CharField(source="get_discovery_source_display", read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "hostname",
            "asset_type",
            "asset_type_display",
            "ip_address",
            "mac_address",
            "operating_system",
            "criticality",
            "exposure",
            "stores_phi",
            "wazuh_agent_id",
            "wazuh_agent_online",
            "discovery_source",
            "discovery_source_display",
            "last_discovered_at",
            "reachable",
            "estado",
            "tags",
            "first_seen",
            "last_seen",
            "open_vulnerability_count",
        ]
        read_only_fields = ["id", "first_seen", "last_seen", "last_discovered_at", "reachable", "discovery_source"]

    def validate_hostname(self, hostname):
        """
        El modelo exige hostname único por organización (ver
        UniqueConstraint en Asset.Meta), pero "organization" no es un
        campo de este serializer -lo asigna la vista a partir del
        usuario autenticado-, así que DRF no puede validar esa
        restricción automáticamente y el duplicado llegaba a la base
        de datos como un IntegrityError (error 500) en vez de un 400
        legible. Se valida aquí a mano contra la organización real.
        """
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None)
        if profile is None:
            return hostname

        qs = Asset.objects.filter(organization=profile.organization, hostname=hostname)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un activo con este hostname en tu organización.")
        return hostname


class DiscoveryRunSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DiscoveryRun
        fields = [
            "id", "source", "source_display", "target", "started_by", "started_at", "finished_at",
            "status", "status_display", "error", "found_count", "new_count", "unreachable_count", "hosts",
        ]
        read_only_fields = fields


class DescubrirSerializer(serializers.Serializer):
    fuente = serializers.ChoiceField(choices=[DiscoverySource.RED_LOCAL, DiscoverySource.WAZUH])
    objetivo = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if data["fuente"] == DiscoverySource.RED_LOCAL and not data.get("objetivo"):
            raise serializers.ValidationError({"objetivo": "Indica el rango de red a barrer (por ejemplo 192.168.1.0/24)."})
        return data
