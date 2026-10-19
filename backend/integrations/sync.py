"""
Orquesta la sincronización: llama a cada conector (wazuh, openvas,
kaspersky), convierte sus NormalizedFinding en registros de Asset y
Vulnerability, y evita duplicados usando (source, external_id).

Se dispara desde una tarea periódica (cron / Celery beat en
producción) o manualmente desde el botón "Sincronizar" de la consola
(ver vulnerabilities.views.SyncSourcesView).
"""

import logging

from assets.models import Asset, AssetType
from vulnerabilities.models import SourceType, Vulnerability, VulnerabilitySource

from . import kaspersky, openvas, wazuh
from .qwen import priority_score

logger = logging.getLogger(__name__)


def _get_or_create_asset(organization, finding) -> Asset:
    asset, _created = Asset.objects.get_or_create(
        organization=organization,
        hostname=finding.asset_hostname,
        defaults={
            "asset_type": AssetType.SERVER,
            "ip_address": finding.asset_ip or None,
        },
    )
    return asset


def _upsert_vulnerability(organization, source: VulnerabilitySource, finding) -> tuple[Vulnerability, bool]:
    asset = _get_or_create_asset(organization, finding)
    defaults = {
        "asset": asset,
        "cve": getattr(finding, "cve", "") or "",
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity,
        "cvss_score": getattr(finding, "cvss_score", None),
    }
    vuln, created = Vulnerability.objects.update_or_create(
        organization=organization,
        source=source,
        external_id=finding.external_id,
        defaults=defaults,
    )
    vuln.priority_score = priority_score(vuln)
    vuln.save(update_fields=["priority_score"])
    return vuln, created


def sync_source(source: VulnerabilitySource) -> dict:
    """Sincroniza una única fuente configurada y devuelve un resumen."""
    fetchers = {
        SourceType.WAZUH: wazuh.fetch_sca_findings,
        SourceType.OPENVAS: lambda: openvas.fetch_scan_results(),
        SourceType.KASPERSKY: kaspersky.fetch_alerts,
    }
    fetch = fetchers.get(source.source_type)
    if fetch is None:
        logger.info("Fuente %s sin sincronización automática (manual).", source.source_type)
        return {"source": source.name, "created": 0, "updated": 0}

    findings = fetch()
    created_count = 0
    updated_count = 0
    for finding in findings:
        _vuln, created = _upsert_vulnerability(source.organization, source, finding)
        created_count += int(created)
        updated_count += int(not created)

    from django.utils import timezone

    source.last_sync_at = timezone.now()
    source.last_sync_ok = True
    source.save(update_fields=["last_sync_at", "last_sync_ok"])

    return {"source": source.name, "created": created_count, "updated": updated_count}


def sync_all_sources(organization) -> list[dict]:
    results = []
    for source in VulnerabilitySource.objects.filter(organization=organization, is_active=True):
        try:
            results.append(sync_source(source))
        except Exception:
            logger.exception("Fallo sincronizando la fuente %s", source.name)
            source.last_sync_ok = False
            source.save(update_fields=["last_sync_ok"])
    return results
