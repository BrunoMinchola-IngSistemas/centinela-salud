import hashlib

from django.http import FileResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin
from governance.audit import registrar
from governance.models import NivelAutonomia

from .models import Evidence
from .serializers import EvidenceSerializer, EvidenceUploadSerializer

ROLES_SUBEN = {Role.ADMIN, Role.COMPLIANCE, Role.IT_OWNER, Role.ANALYST}


class EvidenceViewSet(OrganizationScopedMixin, mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """
    Evidencias: las del flujo de verificación (remediation.verify) y
    las que sube Cumplimiento para un control (HU14). No se editan ni
    se borran, para no romper la trazabilidad de auditoría. El archivo
    se descarga solo a través de la API (con sesión y registro en la
    auditoría): el bucket S3 es privado.
    """

    queryset = Evidence.objects.select_related("vulnerability", "plan", "control")
    serializer_class = EvidenceSerializer
    filterset_fields = ["evidence_type", "source_system", "control", "vulnerability"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    modulo = "evidencias"

    def get_serializer_class(self):
        return EvidenceUploadSerializer if self.action == "create" else EvidenceSerializer

    def create(self, request, *args, **kwargs):
        if request.user.profile.role not in ROLES_SUBEN:
            raise PermissionDenied("Tu rol no puede registrar evidencias.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evidencia = serializer.save(organization=self._organization(), created_by=request.user.username)
        registrar(
            organization=evidencia.organization,
            actor=request.user.username,
            accion="evidencia_cargada",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="control" if evidencia.control_id else "vulnerability",
            objeto_id=evidencia.control_id or evidencia.vulnerability_id,
            detalle={"evidencia_id": str(evidencia.id), "nombre": evidencia.name, "sha256": evidencia.sha256_hash},
        )
        return Response(EvidenceSerializer(evidencia).data, status=201)

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        evidencia = self.get_object()
        if not evidencia.archivo:
            raise NotFound("Esta evidencia no tiene un archivo adjunto (es un registro de reescaneo).")
        contenido = evidencia.archivo.open("rb").read()
        integro = hashlib.sha256(contenido).hexdigest() == evidencia.sha256_hash
        registrar(
            organization=evidencia.organization,
            actor=request.user.username,
            accion="evidencia_descargada",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="evidencia",
            objeto_id=evidencia.id,
            detalle={"integridad_ok": integro},
        )
        nombre = evidencia.nombre_original or evidencia.archivo.name.rsplit("/", 1)[-1]
        evidencia.archivo.close()
        respuesta = FileResponse(iter([contenido]), as_attachment=True, filename=nombre)
        respuesta["X-Integridad-SHA256"] = "ok" if integro else "NO COINCIDE"
        return respuesta
