from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from common.mixins import OrganizationScopedMixin
from common.permissions import exigir_rol
from governance.audit import registrar
from governance.models import NivelAutonomia

from . import asistente, kaspersky, openvas, qwen, wazuh
from .models import FallaIntegracion, RegistroIncompleto
from .normalizacion import OBLIGATORIOS, faltantes, normalizar
from .sync import _upsert, modo_demo


class EstadoIntegracionesView(APIView):
    """
    GET /api/integraciones/estado/ - qué conectores tienen configuración
    en el entorno. Solo dice si hay credenciales y a qué URL apuntan;
    nunca devuelve usuarios, claves ni tokens. Lo usa la consola para
    que TI vea de un vistazo qué falta conectar.
    """

    modulo = "integraciones"

    def get(self, request):
        conectores = [
            {
                "clave": "wazuh",
                "nombre": "Wazuh",
                "descripcion": "Agentes en servidores y estaciones (SCA, vulnerabilidades, integridad).",
                "url": wazuh.WAZUH_API_URL,
                "configurado": bool(wazuh.WAZUH_API_URL and wazuh.WAZUH_API_USER and wazuh.WAZUH_API_PASSWORD),
                "variables": ["WAZUH_API_URL", "WAZUH_API_USER", "WAZUH_API_PASSWORD"],
            },
            {
                "clave": "openvas",
                "nombre": "OpenVAS / GVM",
                "descripcion": "Escáner de vulnerabilidades de red (protocolo GMP).",
                "url": f"{openvas.OPENVAS_GMP_HOST}:{openvas.OPENVAS_GMP_PORT}" if openvas.OPENVAS_GMP_HOST else "",
                "configurado": bool(openvas.OPENVAS_GMP_HOST and openvas.OPENVAS_USERNAME and openvas.OPENVAS_PASSWORD),
                "variables": ["OPENVAS_GMP_HOST", "OPENVAS_GMP_PORT", "OPENVAS_USERNAME", "OPENVAS_PASSWORD"],
            },
            {
                "clave": "qwen",
                "nombre": "Qwen (IA generativa)",
                "descripcion": f"Proveedor: {qwen.QWEN_PROVIDER}. Modelo: {qwen.QWEN_MODEL}.",
                "url": qwen.QWEN_API_URL if qwen.QWEN_PROVIDER == "ollama" else (f"Amazon Bedrock ({qwen.AWS_REGION})" if qwen.QWEN_PROVIDER == "bedrock" else ""),
                "configurado": qwen.disponible(),
                "variables": ["QWEN_PROVIDER", "QWEN_API_URL", "QWEN_MODEL"],
            },
            {
                "clave": "kaspersky",
                "nombre": "Kaspersky (opcional)",
                "descripcion": "Alertas del antivirus/EDR que la clínica ya tenga licenciado.",
                "url": kaspersky.KASPERSKY_API_URL,
                "configurado": bool(kaspersky.KASPERSKY_API_URL and kaspersky.KASPERSKY_API_TOKEN),
                "variables": ["KASPERSKY_API_URL", "KASPERSKY_API_TOKEN"],
            },
        ]
        reales = any(c["configurado"] for c in (conectores[0], conectores[1], conectores[3]))
        return Response({"conectores": conectores, "modo_demo": modo_demo() and not reales, "datos_demostracion": modo_demo()})


class FallaIntegracionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FallaIntegracion
        fields = ["id", "fuente", "fuente_nombre", "error", "ocurrido_en"]


class FallaIntegracionViewSet(OrganizationScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """HU02: log de fallas de la recolección automática."""

    serializer_class = FallaIntegracionSerializer
    queryset = FallaIntegracion.objects.all()
    modulo = "integraciones"


class RegistroIncompletoSerializer(serializers.ModelSerializer):
    fuente_nombre = serializers.CharField(source="fuente.name", read_only=True)
    campos_faltantes_display = serializers.SerializerMethodField()

    def get_campos_faltantes_display(self, obj):
        return [OBLIGATORIOS.get(c, c) for c in obj.campos_faltantes]

    class Meta:
        model = RegistroIncompleto
        fields = [
            "id", "fuente", "fuente_nombre", "external_id", "datos", "campos_faltantes", "campos_faltantes_display",
            "recibido_en", "corregido", "corregido_por", "corregido_en", "vulnerabilidad",
        ]
        read_only_fields = fields


class RegistroIncompletoViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    HU04 esc. 2: registros que llegaron sin campos obligatorios. No
    están en el análisis (no son hallazgos) hasta que alguien de TI
    complete lo que falta con la acción `corregir`.
    """

    serializer_class = RegistroIncompletoSerializer
    queryset = RegistroIncompleto.objects.select_related("fuente")
    filterset_fields = ["corregido"]
    modulo = "integraciones"

    @action(detail=True, methods=["post"])
    def corregir(self, request, pk=None):
        exigir_rol(request, {Role.ADMIN, Role.IT_OWNER, Role.ANALYST}, "Solo TI, el Analista o la Gerencia corrigen registros.")
        registro = self.get_object()
        if registro.corregido:
            raise ValidationError({"detail": "Este registro ya fue corregido."})
        datos = {**registro.datos}
        for campo in ("external_id", "title", "severity", "asset_hostname", "asset_ip", "cve", "cvss_score", "description"):
            if request.data.get(campo) not in (None, ""):
                datos[campo] = request.data[campo]
        d = normalizar(datos)
        if not d["external_id"]:
            d["external_id"] = f"corregido-{registro.id.hex[:12]}"
        falta = faltantes(d)
        if falta:
            raise ValidationError({"campos_faltantes": [OBLIGATORIOS.get(c, c) for c in falta], "detail": "Todavía faltan datos obligatorios."})
        vuln, _ = _upsert(registro.organization, registro.fuente, d)
        registro.corregido = True
        registro.corregido_por = request.user.username
        registro.corregido_en = timezone.now()
        registro.vulnerabilidad = vuln
        registro.save(update_fields=["corregido", "corregido_por", "corregido_en", "vulnerabilidad"])
        registrar(
            organization=registro.organization,
            actor=request.user.username,
            accion="registro_incompleto_corregido",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="vulnerability",
            objeto_id=vuln.id,
            detalle={"fuente": registro.fuente.name, "faltaban": registro.campos_faltantes},
        )
        return Response(RegistroIncompletoSerializer(registro).data)


class PreguntaSerializer(serializers.Serializer):
    pregunta = serializers.CharField(max_length=500)


class AsistenteView(APIView):
    """HU26: POST /api/asistente/preguntar/ {pregunta} -> respuesta basada en los datos recolectados."""

    modulo = "asistente"
    escritura_propia = True  # preguntar no modifica datos: el Auditor también puede

    def post(self, request):
        datos = PreguntaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        respuesta = asistente.responder(request.user.profile.organization, datos.validated_data["pregunta"])
        return Response(respuesta)
