from rest_framework import serializers

from vulnerabilities.models import Vulnerability
from vulnerabilities.serializers import VulnerabilityListSerializer

from .models import RemediationPlan, VerificationAttempt


class VerificationAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationAttempt
        fields = ["id", "requested_at", "requested_by", "vulnerability_still_present", "scan_reference"]
        read_only_fields = ["id", "requested_at"]


class RemediationPlanSerializer(serializers.ModelSerializer):
    vulnerability_detail = VulnerabilityListSerializer(source="vulnerability", read_only=True)
    verification_attempts = VerificationAttemptSerializer(many=True, read_only=True)
    # Opcional al crear: si no se envía, la vista lo calcula a partir
    # de la severidad (ver RemediationPlanViewSet.perform_create).
    due_date = serializers.DateField(required=False)

    class Meta:
        model = RemediationPlan
        fields = [
            "id",
            "vulnerability",
            "vulnerability_detail",
            "owner_name",
            "owner_email",
            "status",
            "due_date",
            "notes",
            "created_at",
            "updated_at",
            "verification_attempts",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_vulnerability(self, vulnerability: Vulnerability):
        if hasattr(vulnerability, "plan"):
            raise serializers.ValidationError("Esta vulnerabilidad ya tiene un plan de corrección.")
        return vulnerability
