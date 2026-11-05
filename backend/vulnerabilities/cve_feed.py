"""
HU03: base de conocimiento de vulnerabilidades actualizada.

Fuentes reconocidas (públicas y gratuitas):
- NVD (NIST) API 2.0: CVE publicadas o modificadas en las últimas N horas.
  https://nvd.nist.gov/developers/vulnerabilities
- CISA KEV: catálogo de vulnerabilidades explotadas activamente.
  https://www.cisa.gov/known-exploited-vulnerabilities-catalog

La tarea programada (common/management/commands/programador.py) la
corre cada 6 horas, así una CVE nueva entra a la base en menos de 24 h.
Si una fuente no responde, no se borra nada (se conserva la última
versión) y se avisa a TI que la sincronización no se completó.

Además "enriquece" los hallazgos de las clínicas: si una CVE de un
hallazgo pasa a estar en KEV, se marca la explotación activa (regla R4)
y se recalcula su prioridad; si el hallazgo no tenía CVSS, toma el
vector de la NVD.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import requests
from django.utils import timezone

from .cvss import puntaje_desde_vector, severidad_desde_puntaje
from .models import CatalogoCVE, SincronizacionCVE, Vulnerability

logger = logging.getLogger(__name__)

NVD_URL = os.getenv("NVD_API_URL", "https://services.nvd.nist.gov/rest/json/cves/2.0")
NVD_API_KEY = os.getenv("NVD_API_KEY", "")
KEV_URL = os.getenv(
    "KEV_URL", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
)
TIMEOUT = (5, 60)
POR_PAGINA = 2000


def _fecha_nvd(dt):
    return dt.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def _parse_fecha(texto):
    if not texto:
        return None
    dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)


def _descargar_nvd(desde, hasta):
    """Devuelve la lista de objetos `cve` de la NVD modificados en el rango (paginando)."""
    headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else {}
    inicio, total, salida = 0, None, []
    while total is None or inicio < total:
        resp = requests.get(
            NVD_URL,
            params={
                "lastModStartDate": _fecha_nvd(desde),
                "lastModEndDate": _fecha_nvd(hasta),
                "startIndex": inicio,
                "resultsPerPage": POR_PAGINA,
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        datos = resp.json()
        total = datos.get("totalResults", 0)
        salida += [item["cve"] for item in datos.get("vulnerabilities", [])]
        inicio += POR_PAGINA
        if inicio < total and not NVD_API_KEY:
            time.sleep(6)  # límite público de la NVD: 5 peticiones cada 30 s
    return salida


def _descargar_kev():
    resp = requests.get(KEV_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("vulnerabilities", [])


def _metricas(cve):
    metricas = cve.get("metrics", {})
    for clave in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30"):
        if metricas.get(clave):
            datos = metricas[clave][0].get("cvssData", {})
            return datos.get("baseScore"), datos.get("vectorString", ""), (datos.get("baseSeverity") or "").lower()
    return None, "", ""


def _descripcion(cve):
    textos = {d.get("lang"): d.get("value", "") for d in cve.get("descriptions", [])}
    return textos.get("es") or textos.get("en") or ""


def _guardar_nvd(cves):
    nuevos = actualizados = 0
    for cve in cves:
        puntaje, vector, severidad = _metricas(cve)
        _, creado = CatalogoCVE.objects.update_or_create(
            cve_id=cve["id"],
            defaults={
                "descripcion": _descripcion(cve)[:4000],
                "cvss_score": puntaje,
                "cvss_vector": vector,
                "severidad": severidad,
                "publicado_en": _parse_fecha(cve.get("published")),
                "modificado_en": _parse_fecha(cve.get("lastModified")),
                "fuente": "nvd",
            },
        )
        nuevos += int(creado)
        actualizados += int(not creado)
    return nuevos, actualizados


def _guardar_kev(entradas):
    marcados = 0
    for e in entradas:
        cve_id = e.get("cveID")
        if not cve_id:
            continue
        fecha = e.get("dateAdded")
        obj, creado = CatalogoCVE.objects.get_or_create(cve_id=cve_id, defaults={"fuente": "kev"})
        if not obj.kev:
            obj.kev = True
            obj.kev_agregado_en = datetime.strptime(fecha, "%Y-%m-%d").date() if fecha else None
            if creado and e.get("shortDescription"):
                obj.descripcion = e["shortDescription"][:4000]
            obj.save()
            marcados += 1
    return marcados


def enriquecer_hallazgos():
    """Aplica la base CVE a los hallazgos de todas las clínicas (corre como tarea, sin RLS de usuario)."""
    enriquecidos = 0
    catalogo = {c.cve_id: c for c in CatalogoCVE.objects.filter(cve_id__in=Vulnerability.objects.exclude(cve="").values("cve"))}
    for v in Vulnerability.objects.exclude(cve="").exclude(status="closed").select_related("asset"):
        c = catalogo.get(v.cve)
        if c is None:
            continue
        cambios = []
        if c.kev and not v.actively_exploited:
            v.actively_exploited = True
            cambios.append("actively_exploited")
        if v.cvss_score is None and not v.cvss_vector and c.cvss_vector and puntaje_desde_vector(c.cvss_vector) is not None:
            v.cvss_vector = c.cvss_vector
            cambios.append("cvss_vector")
        elif v.cvss_score is None and c.cvss_score is not None:
            v.cvss_score = c.cvss_score
            v.severity = severidad_desde_puntaje(c.cvss_score)
            cambios += ["cvss_score", "severity"]
        if cambios:
            v.save(update_fields=cambios)
            enriquecidos += 1
    return enriquecidos


def sincronizar(horas=24, ahora=None):
    ahora = ahora or timezone.now()
    sync = SincronizacionCVE.objects.create()
    try:
        cves = _descargar_nvd(ahora - timedelta(hours=horas), ahora)
        kev = _descargar_kev()
        sync.nuevos, sync.actualizados = _guardar_nvd(cves)
        sync.kev_marcados = _guardar_kev(kev)
        sync.hallazgos_enriquecidos = enriquecer_hallazgos()
        sync.ok = True
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Sincronización CVE incompleta: %s", exc)
        sync.ok = False
        sync.error = f"{type(exc).__name__}: {exc}"[:2000]
        _avisar_fallo(sync)
    sync.terminado_en = timezone.now()
    sync.save()
    return sync


def _avisar_fallo(sync):
    from accounts.models import Organization
    from notificaciones.models import NivelNotificacion, TipoNotificacion
    from notificaciones.servicios import notificar

    ultima_ok = SincronizacionCVE.objects.filter(ok=True).order_by("-terminado_en").first()
    desde = f"la del {timezone.localtime(ultima_ok.terminado_en):%d/%m/%Y %H:%M}" if ultima_ok else "la carga inicial"
    for org in Organization.objects.all():
        notificar(
            organization=org,
            tipo=TipoNotificacion.CVE,
            nivel=NivelNotificacion.ADVERTENCIA,
            titulo="La sincronización de la base CVE no se completó",
            mensaje=f"La fuente externa no respondió. Se conserva la última versión disponible ({desde}). Error: {sync.error[:200]}",
            enlace="/fuentes",
            enviar_email=False,
        )
