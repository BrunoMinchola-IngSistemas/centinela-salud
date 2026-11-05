"""
HU20: Risk Score en lenguaje no técnico, con semáforo.

Cómo se calcula (0 = sin riesgo, 100 = máximo):

  carga      = suma, por cada hallazgo abierto, del peso de su prioridad
               contextual (crítica 10 · alta 6 · media 3 · baja 1),
               multiplicado por 1.5 si el activo guarda datos clínicos.
  exposición = 100 · (1 - e^(-carga/40))   -> crece rápido con los
               primeros hallazgos graves y se satura cerca de 100.
  Risk Score = 0.7 · exposición + 0.3 · (100 - % de cumplimiento ISO)

Semáforo: verde < 35 · ámbar 35-64 · rojo >= 65.

Pesos y umbrales son una propuesta para validar con el asesor (igual
que R1-R5); están todos aquí para poder ajustarlos en un solo lugar.
"""

import math
from datetime import timedelta

from django.utils import timezone

from controls.services import cumplimiento_global, cumplimiento_ley_29733, cumplimiento_por_dominio
from vulnerabilities.models import Vulnerability, VulnerabilityStatus

PESO = {"critical": 10, "high": 6, "medium": 3, "low": 1, "none": 0}
FACTOR_DATOS_CLINICOS = 1.5
ESCALA = 40
PESO_EXPOSICION = 0.7
UMBRAL_AMBAR = 35
UMBRAL_ROJO = 65

SEMAFORO = {
    "verde": ("Bajo", "La clínica tiene su riesgo bajo control. Mantener el monitoreo."),
    "ambar": ("Moderado", "Hay problemas que conviene resolver pronto para no exponer la atención ni los datos de pacientes."),
    "rojo": ("Alto", "Hay problemas graves sin resolver: se recomienda priorizar recursos para corregirlos de inmediato."),
}


def _nivel(v):
    return v.contextual_priority or v.severity or "medium"


def abiertas(organization):
    return Vulnerability.objects.filter(organization=organization).exclude(status=VulnerabilityStatus.CLOSED).select_related("asset")


def risk_score(organization):
    lista = list(abiertas(organization))
    carga = sum(
        PESO.get(_nivel(v), 3) * (FACTOR_DATOS_CLINICOS if v.asset and v.asset.stores_phi else 1) for v in lista
    )
    exposicion = round(100 * (1 - math.exp(-carga / ESCALA)))
    cumplimiento = cumplimiento_global(organization)
    score = round(PESO_EXPOSICION * exposicion + (1 - PESO_EXPOSICION) * (100 - cumplimiento))
    color = "verde" if score < UMBRAL_AMBAR else "ambar" if score < UMBRAL_ROJO else "rojo"
    nivel, consejo = SEMAFORO[color]
    graves = sum(1 for v in lista if _nivel(v) in ("critical", "high"))
    mensaje = (
        f"Riesgo {nivel.lower()}: hay {graves} problema(s) grave(s) sin resolver de {len(lista)} abiertos, "
        f"y la clínica cumple el {cumplimiento} % de los controles de seguridad. {consejo}"
    )
    return {
        "score": score,
        "semaforo": color,
        "nivel": nivel,
        "mensaje": mensaje,
        "exposicion": exposicion,
        "cumplimiento": cumplimiento,
        "abiertas": len(lista),
        "graves": graves,
        "criticas": sum(1 for v in lista if _nivel(v) == "critical"),
    }


def registrar_snapshot(organization, fecha=None):
    from .models import SnapshotRiesgo

    r = risk_score(organization)
    snap, _ = SnapshotRiesgo.objects.update_or_create(
        organization=organization,
        fecha=fecha or timezone.localdate(),
        defaults={
            "risk_score": r["score"],
            "exposicion": r["exposicion"],
            "cumplimiento_global": r["cumplimiento"],
            "abiertas": r["abiertas"],
            "criticas": r["criticas"],
        },
    )
    return snap


NIVEL_TEXTO = {"critical": "muy grave", "high": "grave", "medium": "moderado", "low": "menor"}


def principales_riesgos(organization, n=3):
    orden = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
    lista = sorted(abiertas(organization), key=lambda v: (orden.get(_nivel(v), 2), -v.priority_score))[:n]
    salida = []
    for v in lista:
        equipo = v.asset.hostname if v.asset else "un equipo aún no identificado"
        datos = " que guarda datos de pacientes" if v.asset and v.asset.stores_phi else ""
        salida.append(
            {
                "id": v.id,
                "texto": f"El equipo {equipo}{datos} tiene un problema {NIVEL_TEXTO.get(_nivel(v), 'moderado')}: {v.title}.",
                "nivel": _nivel(v),
            }
        )
    return salida


def resumen_ejecutivo(organization):
    from governance.models import EstadoSolicitud, SolicitudAprobacion
    from incidents.models import IncidenteReportado

    from .models import SnapshotRiesgo

    riesgo = risk_score(organization)
    snaps = list(SnapshotRiesgo.objects.filter(organization=organization).order_by("fecha"))
    base = snaps[0] if snaps else None
    hoy = timezone.localdate()
    hace_30 = timezone.now() - timedelta(days=30)
    vencidas = [v for v in abiertas(organization).select_related("plan") if v.is_overdue]
    return {
        "organizacion": organization.name,
        "riesgo": riesgo,
        "cumplimiento_global": cumplimiento_global(organization),
        "cumplimiento_ley_29733": cumplimiento_ley_29733(organization),
        "por_dominio": cumplimiento_por_dominio(organization),
        "linea_base": (
            {"fecha": base.fecha, "risk_score": base.risk_score, "cumplimiento": base.cumplimiento_global} if base else None
        ),
        "variacion_vs_linea_base": (riesgo["score"] - base.risk_score) if base else None,
        "historial": [
            {"fecha": s.fecha, "risk_score": s.risk_score, "cumplimiento": s.cumplimiento_global} for s in snaps[-90:]
        ],
        "principales_riesgos": principales_riesgos(organization),
        "aprobaciones_pendientes": SolicitudAprobacion.objects.filter(
            plan__vulnerability__organization=organization,
            estado__in=[EstadoSolicitud.PENDIENTE, EstadoSolicitud.ESCALADA],
        ).count(),
        "vencidos": len(vencidas),
        "incidentes_30_dias": IncidenteReportado.objects.filter(organization=organization, creado_en__gte=hace_30).count(),
        "fecha": hoy,
        "actualizado_en": timezone.now(),
    }
