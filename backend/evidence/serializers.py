import hashlib

from django.conf import settings
from rest_framework import serializers

from common.privacidad import seudonimizar_texto
from common.serializers import OrganizationScopedRelationsMixin

from .models import Evidence, EvidenceType

# HU14 esc. 2: formatos permitidos y su "firma" (primeros bytes) para no
# confiar solo en la extensión que manda el navegador.
FORMATOS = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "docx": [b"PK\x03\x04"],
    "xlsx": [b"PK\x03\x04"],
    "csv": None,  # texto
    "txt": None,
}
TAMANO_MAXIMO = 10 * 1024 * 1024
MENSAJE_FORMATO = "Formato de archivo no válido. Se permiten PDF, PNG, JPG, DOCX, XLSX, CSV o TXT de hasta 10 MB."


class EvidenceSerializer(OrganizationScopedRelationsMixin, serializers.ModelSerializer):
    vulnerability_cve = serializers.CharField(source="vulnerability.cve", read_only=True, default="")
    control_codigo = serializers.CharField(source="control.iso_code", read_only=True, default="")
    control_nombre = serializers.CharField(source="control.name", read_only=True, default="")
    evidence_type_display = serializers.CharField(source="get_evidence_type_display", read_only=True)
    tiene_archivo = serializers.SerializerMethodField()

    def get_tiene_archivo(self, obj):
        return bool(obj.archivo)

    class Meta:
        model = Evidence
        fields = [
            "id",
            "name",
            "evidence_type",
            "evidence_type_display",
            "vulnerability",
            "vulnerability_cve",
            "plan",
            "control",
            "control_codigo",
            "control_nombre",
            "descripcion",
            "nombre_original",
            "tamano_bytes",
            "tiene_archivo",
            "s3_bucket",
            "s3_key",
            "sha256_hash",
            "source_system",
            "created_at",
            "created_by",
        ]
        read_only_fields = fields


class EvidenceUploadSerializer(OrganizationScopedRelationsMixin, serializers.ModelSerializer):
    """HU14: alta de una evidencia con archivo (multipart/form-data)."""

    archivo = serializers.FileField(write_only=True)
    evidence_type = serializers.ChoiceField(choices=EvidenceType.choices, default=EvidenceType.OTHER)

    class Meta:
        model = Evidence
        fields = ["name", "evidence_type", "control", "vulnerability", "descripcion", "archivo"]
        extra_kwargs = {"control": {"required": False}, "vulnerability": {"required": False}}

    def validate_archivo(self, archivo):
        nombre = archivo.name or ""
        extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        if extension not in FORMATOS or archivo.size > TAMANO_MAXIMO or archivo.size == 0:
            raise serializers.ValidationError(MENSAJE_FORMATO)
        firmas = FORMATOS[extension]
        inicio = archivo.read(8)
        archivo.seek(0)
        if firmas is not None and not any(inicio.startswith(f) for f in firmas):
            raise serializers.ValidationError(MENSAJE_FORMATO)
        if firmas is None and b"\x00" in archivo.read(4096):
            archivo.seek(0)
            raise serializers.ValidationError(MENSAJE_FORMATO)
        archivo.seek(0)
        return archivo

    def validate(self, data):
        if not data.get("control") and not data.get("vulnerability"):
            raise serializers.ValidationError({"control": "Asocia la evidencia a un control (o a un hallazgo)."})
        return data

    def create(self, validated_data):
        archivo = validated_data.pop("archivo")
        descripcion = validated_data.pop("descripcion", "")
        sha = hashlib.sha256()
        for trozo in archivo.chunks():
            sha.update(trozo)
        archivo.seek(0)
        evidencia = Evidence(
            **validated_data,
            sha256_hash=sha.hexdigest(),
            nombre_original=seudonimizar_texto(archivo.name)[:255],
            tamano_bytes=archivo.size,
            descripcion=seudonimizar_texto(descripcion),
            source_system="Carga manual",
            s3_bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") or "almacenamiento-local",
        )
        evidencia.archivo.save(archivo.name, archivo, save=False)
        evidencia.s3_key = evidencia.archivo.name
        evidencia.save()
        return evidencia
