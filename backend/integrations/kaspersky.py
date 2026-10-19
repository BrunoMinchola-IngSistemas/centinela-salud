"""
Conector OPCIONAL hacia Kaspersky (Kaspersky Security Center u otro
EDR/antivirus que la PyME ya tenga licenciado). No reemplaza a OpenVAS
como motor de escaneo de vulnerabilidades: Kaspersky Internet
Security/Total Security no expone una API de vulnerabilidades para
integrarse aquí (su función "Vulnerability Scan" es local al equipo,
sin API REST).

Este módulo queda como punto de extensión: si la clínica usa
Kaspersky Security Center (la consola de administración central, que
sí tiene una API vía openapi/KSCGate), sus alertas de malware/EDR se
pueden normalizar aquí como una fuente más en VulnerabilitySource.
"""

import logging
import os

logger = logging.getLogger(__name__)

KASPERSKY_API_URL = os.getenv("KASPERSKY_API_URL", "")
KASPERSKY_API_TOKEN = os.getenv("KASPERSKY_API_TOKEN", "")


def fetch_alerts() -> list:
    if not KASPERSKY_API_URL:
        logger.info("Kaspersky no configurado; se omite (integración opcional).")
        return []
    logger.warning(
        "fetch_alerts: Kaspersky Security Center expone su API vía KSCGate/OpenAPI. "
        "Implementar aquí cuando la organización confirme que lo usa y comparta el endpoint."
    )
    return []
