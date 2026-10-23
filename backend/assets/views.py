import csv

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin

from .discovery import ObjetivoInvalido, ejecutar_descubrimiento
from .models import Asset, AssetStatus, AssetType, Criticality, DiscoveryRun
from .serializers import AssetSerializer, DescubrirSerializer, DiscoveryRunSerializer

ROLES_DESCUBREN = {Role.ADMIN, Role.IT_OWNER}


class AssetViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """
    CRUD de activos. En producción, la mayoría se crean automáticamente
    cuando Wazuh u OpenVAS reportan un host nuevo (ver integrations.sync)
    o cuando el Administrador / TI lanza un descubrimiento (acción
    `descubrir`). `informe` resume el estado del parque tecnológico y lo
    exporta a CSV.
    """

    queryset = Asset.objects.all().order_by("hostname")
    serializer_class = AssetSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["asset_type", "criticality", "stores_phi", "wazuh_agent_online", "discovery_source"]
    search_fields = ["hostname", "ip_address", "operating_system", "mac_address"]

    @action(detail=False, methods=["post"])
    def descubrir(self, request):
        if request.user.profile.role not in ROLES_DESCUBREN:
            raise PermissionDenied("Solo el Administrador o el Responsable de TI pueden lanzar un descubrimiento de activos.")
        serializer = DescubrirSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = ejecutar_descubrimiento(
                organization=self._organization(),
                fuente=serializer.validated_data["fuente"],
                objetivo=serializer.validated_data.get("objetivo", ""),
                actor=request.user.username,
            )
        except ObjetivoInvalido as exc:
            raise ValidationError({"objetivo": str(exc)}) from exc
        return Response(DiscoveryRunSerializer(run).data, status=201)

    @action(detail=False, methods=["get"])
    def informe(self, request):
        """Resumen del inventario: por tipo, estado, criticidad, cobertura de agentes y riesgo. `?formato=csv` lo exporta."""
        qs = self.get_queryset().prefetch_related("vulnerabilities")
        activos = list(qs)

        if request.query_params.get("formato") == "csv":
            return self._csv(activos)

        def cuenta(pred):
            return sum(1 for a in activos if pred(a))

        por_tipo = [
            {"clave": t.value, "etiqueta": t.label, "total": cuenta(lambda a, t=t: a.asset_type == t)}
            for t in AssetType
        ]
        por_estado = [
            {"clave": e.value, "etiqueta": e.label, "total": cuenta(lambda a, e=e: a.estado == e)}
            for e in AssetStatus
        ]
        por_criticidad = [
            {"clave": c.value, "etiqueta": c.label, "total": cuenta(lambda a, c=c: a.criticality == c)}
            for c in Criticality
        ]
        riesgo = sorted(
            (
                {"id": str(a.id), "hostname": a.hostname, "asset_type": a.asset_type, "criticality": a.criticality,
                 "estado": a.estado, "stores_phi": a.stores_phi, "abiertas": a.open_vulnerability_count}
                for a in activos
            ),
            key=lambda r: (-r["abiertas"], r["hostname"]),
        )[:10]
        ultimo = DiscoveryRun.objects.filter(organization=self._organization()).first()

        return Response(
            {
                "generado_en": timezone.now(),
                "total": len(activos),
                "por_tipo": por_tipo,
                "por_estado": por_estado,
                "por_criticidad": por_criticidad,
                "con_datos_pacientes": cuenta(lambda a: a.stores_phi),
                "con_agente": cuenta(lambda a: bool(a.wazuh_agent_id) or a.wazuh_agent_online),
                "agente_en_linea": cuenta(lambda a: a.wazuh_agent_online),
                "sin_verificar": cuenta(lambda a: a.estado == AssetStatus.DESCONOCIDO),
                "con_vulnerabilidades_abiertas": cuenta(lambda a: a.open_vulnerability_count > 0),
                "mayor_riesgo": riesgo,
                "ultimo_descubrimiento": DiscoveryRunSerializer(ultimo).data if ultimo else None,
            }
        )

    def _csv(self, activos):
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="inventario-activos-{timezone.now():%Y%m%d-%H%M}.csv"'
        resp.write("﻿")  # BOM para que Excel abra los acentos bien
        writer = csv.writer(resp, delimiter=";")
        writer.writerow(
            ["Activo", "Tipo", "IP", "MAC", "Sistema", "Criticidad", "Exposición", "Datos de pacientes", "Estado",
             "Agente Wazuh", "Origen", "Último descubrimiento", "Vulnerabilidades abiertas"]
        )
        for a in activos:
            writer.writerow(
                [
                    a.hostname, a.get_asset_type_display(), a.ip_address or "", a.mac_address, a.operating_system,
                    a.get_criticality_display(), a.get_exposure_display(), "Sí" if a.stores_phi else "No",
                    AssetStatus(a.estado).label, "En línea" if a.wazuh_agent_online else ("Registrado" if a.wazuh_agent_id else "Sin agente"),
                    a.get_discovery_source_display(),
                    timezone.localtime(a.last_discovered_at).strftime("%Y-%m-%d %H:%M") if a.last_discovered_at else "",
                    a.open_vulnerability_count,
                ]
            )
        return resp


class DiscoveryRunViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Historial de descubrimientos (informes). Solo lectura: se crean con POST /api/assets/descubrir/."""

    queryset = DiscoveryRun.objects.all()
    serializer_class = DiscoveryRunSerializer
