from rest_framework import serializers

from .models import Evidence


class EvidenceSerializer(serializers.ModelSerializer):
    vulnerability_cve = serializers.CharField(source="vulnerability.cve", read_only=True, default="")

    class Meta:
        model = Evidence
        fields = [
            "id",
            "name",
            "evidence_type",
            "vulnerability",
            "vulnerability_cve",
            "plan",
            "s3_bucket",
            "s3_key",
            "sha256_hash",
            "source_system",
            "created_at",
            "created_by",
        ]
        read_only_fields = fields
