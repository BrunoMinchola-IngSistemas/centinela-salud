"""
Orquesta la recolección automática (HU02): llama a cada conector
(Wazuh, OpenVAS, Kaspersky), lleva lo que devuelven al esquema único
(HU04, ver normalizacion.py) y lo convierte en Asset y Vulnerability,
sin duplicar (fuente + external_id).

- Si una fuente falla, se anota en FallaIntegracion ("log de fallas")
  y se sigue con las demás.
- Si un registro llega sin campos obligatorios, se guarda como
  RegistroIncompleto y no entra al análisis hasta que se corrija.
- Si aparece un activo que no estaba en el inventario, se avisa a TI
  (HU05) en el mismo momento.

Se dispara desde la tarea programada (cada 6 h, ver
common/management/commands/programador.py) o desde el botón
"Sincronizar" de la consola.
"""

import logging

from django.conf import settings
from django.utils import timezone

from assets.models import Asset, AssetType, DiscoverySource
from vulnerabilities.models import SourceType, Vulnerability, VulnerabilitySource

from . import demo, kaspersky, openvas, wazuh
from .models import FallaIntegracion, RegistroIncompleto
from .normalizacion import faltantes, normalizar
from .qwen import priority_score

logger = logging.getLogger(__name__)


class ConexionFuenteError(Exception):
    """La fuente está configurada pero no respondió como se esperaba."""


def modo_demo():
    return getattr(settings, "INTEGRACIONES_DEMO", False)


def _configurado(tipo):
    # Configurado = URL + credenciales (igual que /api/integraciones/estado/).
    return {
        SourceType.WAZUH: bool(wazuh.WAZUH_API_URL and wazuh.WAZUH_API_USER and wazuh.WAZUH_API_PASSWORD),
        SourceType.OPENVAS: bool(openvas.OPENVAS_GMP_HOST and openvas.OPENVAS_USERNAME and openvas.OPENVAS_PASSWORD),
        SourceType.KASPERSKY: bool(kaspersky.KASPERSKY_API_URL and kaspersky.KASPERSKY_API_TOKEN),
    }.get(tipo, False)


def _traer(source):
    """Hallazgos crudos de la fuente (reales si está configurada; de demostración si no y el modo demo está activo)."""
    tipo = source.source_type
    if tipo == SourceType.MANUAL:
        return None
    if not _configurado(tipo):
        return demo.hallazgos(tipo) if modo_demo() else []
    fetchers = {
        SourceType.WAZUH: wazuh.fetch_sca_findings,
        SourceType.OPENVAS: openvas.fetch_scan_results,
        SourceType.KASPERSKY: kaspersky.fetch_alerts,
    }
    return fetchers[tipo]()


def _activo(organization, d):
    """Busca el activo por IP o hostname; si no existe, lo crea y avisa a TI (HU05)."""
    asset = None
    if d["asset_ip"]:
        asset = Asset.objects.filter(organization=organization, ip_address=d["asset_ip"]).first()
    if asset is None and d["asset_hostname"]:
        asset = Asset.objects.filter(organization=organization, hostname__iexact=d["asset_hostname"]).first()
    if asset is not None:
        return asset, False
    asset = Asset.objects.create(
        organization=organization,
        hostname=d["asset_hostname"] or d["asset_ip"],
        asset_type=AssetType.SERVER,
        ip_address=d["asset_ip"] or None,
        discovery_source=DiscoverySource.MANUAL,
        last_discovered_at=timezone.now(),
    )
    from assets.discovery import avisar_activo_nuevo

    avisar_activo_nuevo(organization, asset, origen="la sincronización de fuentes")
    return asset, True


def _upsert(organization, source, d):
    asset, _ = _activo(organization, d)
    defaults = {
        "asset": asset,
        "cve": d["cve"],
        "title": d["title"],
        "description": d["description"],
        "severity": d["severity"],
        "cvss_score": d["cvss_score"],
        "cvss_vector": d["cvss_vector"],
        "epss_score": d["epss_score"],
    }
    if d["category"]:
        defaults["category"] = d["category"]
    vuln, created = Vulnerability.objects.update_or_create(
        organization=organization, source=source, external_id=d["external_id"], defaults=defaults
    )
    vuln.priority_score = priority_score(vuln)
    vuln.save(update_fields=["priority_score"])
    return vuln, created


def sync_source(source: VulnerabilitySource) -> dict:
    """Sincroniza una única fuente configurada y devuelve un resumen."""
    crudos = _traer(source)
    if crudos is None:
        return {"source": source.name, "created": 0, "updated": 0, "incompletos": 0, "omitida": True}

    creados = actualizados = incompletos = 0
    for crudo in crudos:
        d = normalizar(crudo)
        falta = faltantes(d)
        if falta:
            RegistroIncompleto.objects.update_or_create(
                organization=source.organization,
                fuente=source,
                external_id=d["external_id"],
                corregido=False,
                defaults={"datos": {k: (str(v) if v is not None else None) for k, v in d.items()}, "campos_faltantes": falta},
            )
            incompletos += 1
            continue
        _, created = _upsert(source.organization, source, d)
        creados += int(created)
        actualizados += int(not created)

    source.last_sync_at = timezone.now()
    source.last_sync_ok = True
    source.save(update_fields=["last_sync_at", "last_sync_ok"])
    return {
        "source": source.name,
        "created": creados,
        "updated": actualizados,
        "incompletos": incompletos,
        "demo": not _configurado(source.source_type) and modo_demo(),
    }


def sync_all_sources(organization) -> list[dict]:
    results = []
    for source in VulnerabilitySource.objects.filter(organization=organization, is_active=True):
        try:
            results.append(sync_source(source))
        except Exception as exc:  # noqa: BLE001 - HU02: anotar la falla y seguir con las demás fuentes
            logger.exception("Fallo sincronizando la fuente %s", source.name)
            source.last_sync_ok = False
            source.last_sync_at = timezone.now()
            source.save(update_fields=["last_sync_ok", "last_sync_at"])
            FallaIntegracion.objects.create(
                organization=organization, fuente=source, fuente_nombre=source.name, error=f"{type(exc).__name__}: {exc}"[:2000]
            )
            results.append({"source": source.name, "error": str(exc)[:300], "created": 0, "updated": 0})
    return results


def recolectar_todas():
    """Tarea programada: recolección automática para todas las organizaciones."""
    from accounts.models import Organization

    return {str(org.id): sync_all_sources(org) for org in Organization.objects.all()}

