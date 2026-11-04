from rest_framework.response import Response
from rest_framework.views import APIView

from . import kaspersky, openvas, qwen, wazuh


class EstadoIntegracionesView(APIView):
    """
    GET /api/integraciones/estado/ - qué conectores tienen configuración
    en el entorno (.env). Solo dice si hay credenciales y a qué URL
    apuntan; nunca devuelve usuarios, claves ni tokens. Lo usa
    Configuración > Integraciones para que TI vea de un vistazo qué
    falta conectar.
    """

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
                "nombre": "Qwen (IA local)",
                "descripcion": f"Modelo de lenguaje en la sede del cliente. Modelo: {qwen.QWEN_MODEL}.",
                "url": qwen.QWEN_API_URL,
                "configurado": bool(qwen.QWEN_API_URL),
                "variables": ["QWEN_API_URL", "QWEN_MODEL"],
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
        return Response({"conectores": conectores, "modo_demo": not any(c["configurado"] for c in conectores[:2])})
