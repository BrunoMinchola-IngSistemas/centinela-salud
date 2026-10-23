"""
Cliente hacia la API REST de Wazuh (manager en AWS). Trae alertas y
resultados de SCA (Security Configuration Assessment) y los normaliza
al formato interno que usa el modelo Vulnerability.

Documentación oficial: https://documentation.wazuh.com/current/user-manual/api/reference.html
"""

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

WAZUH_API_URL = os.getenv("WAZUH_API_URL", "")
WAZUH_API_USER = os.getenv("WAZUH_API_USER", "")
WAZUH_API_PASSWORD = os.getenv("WAZUH_API_PASSWORD", "")


@dataclass
class NormalizedFinding:
    external_id: str
    asset_hostname: str
    asset_ip: str
    title: str
    description: str
    severity: str
    cve: str = ""


def _get_token() -> str | None:
    if not WAZUH_API_URL:
        return None
    try:
        resp = requests.post(
            f"{WAZUH_API_URL}/security/user/authenticate",
            auth=(WAZUH_API_USER, WAZUH_API_PASSWORD),
            verify=True,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["token"]
    except requests.RequestException:
        logger.warning("No se pudo autenticar contra Wazuh en %s", WAZUH_API_URL)
        return None


@dataclass
class WazuhAgent:
    agent_id: str
    name: str
    ip: str
    os_name: str
    online: bool


def fetch_agents() -> list[WazuhAgent]:
    """
    Inventario de agentes registrados en el manager, para el
    descubrimiento de activos. Devuelve lista vacía si Wazuh no está
    configurado en este entorno.
    """
    token = _get_token()
    if not token:
        logger.info("Wazuh no configurado en este entorno; descubrimiento por agentes omitido.")
        return []
    try:
        resp = requests.get(
            f"{WAZUH_API_URL}/agents",
            headers={"Authorization": f"Bearer {token}"},
            params={"select": "id,name,ip,os.name,status", "limit": 500},
            timeout=15,
        )
        resp.raise_for_status()
        agents = []
        for agent in resp.json()["data"]["affected_items"]:
            if agent.get("id") == "000":  # el propio manager
                continue
            agents.append(
                WazuhAgent(
                    agent_id=agent.get("id", ""),
                    name=agent.get("name", agent.get("id", "")),
                    ip=agent.get("ip", "") or "",
                    os_name=(agent.get("os") or {}).get("name", ""),
                    online=agent.get("status") == "active",
                )
            )
        return agents
    except requests.RequestException:
        logger.exception("Error consultando los agentes de Wazuh")
        return []


def fetch_sca_findings() -> list[NormalizedFinding]:
    """
    Trae los resultados fallidos de Security Configuration Assessment
    de todos los agentes y los devuelve ya normalizados. Esta función
    se llama desde una tarea periódica (ver integrations/sync.py).
    """
    token = _get_token()
    if not token:
        logger.info("Wazuh no configurado en este entorno; sync omitido.")
        return []

    headers = {"Authorization": f"Bearer {token}"}
    findings: list[NormalizedFinding] = []
    try:
        agents_resp = requests.get(f"{WAZUH_API_URL}/agents", headers=headers, timeout=15)
        agents_resp.raise_for_status()
        for agent in agents_resp.json()["data"]["affected_items"]:
            agent_id = agent["id"]
            sca_resp = requests.get(
                f"{WAZUH_API_URL}/sca/{agent_id}",
                headers=headers,
                params={"result": "failed"},
                timeout=15,
            )
            sca_resp.raise_for_status()
            for policy in sca_resp.json()["data"]["affected_items"]:
                findings.append(
                    NormalizedFinding(
                        external_id=f"wazuh-sca-{agent_id}-{policy.get('policy_id')}",
                        asset_hostname=agent.get("name", agent_id),
                        asset_ip=agent.get("ip", ""),
                        title=policy.get("name", "Hallazgo de configuración"),
                        description=policy.get("description", ""),
                        severity="medium",
                    )
                )
    except requests.RequestException:
        logger.exception("Error consultando la API de Wazuh")
    return findings
