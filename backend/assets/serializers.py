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
