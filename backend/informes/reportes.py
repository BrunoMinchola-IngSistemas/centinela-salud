"""
HU21: reporte periódico (PDF y Excel) con resumen de vulnerabilidades,
cumplimiento y remediación. La primera página del PDF es el resumen
ejecutivo de una página.
"""

import hashlib
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import Organization, PeriodicidadReporte
from controls.services import cumplimiento_por_dominio, recomendaciones
from governance.audit import registrar
from governance.models import NivelAutonomia
from notificaciones.models import TipoNotificacion
from notificaciones.servicios import notificar
from remediation.models import RemediationPlan
from vulnerabilities.models import Vulnerability, VulnerabilityStatus

from .exportar import pdf_bytes, xlsx_bytes
from .indicadores import principales_riesgos, registrar_snapshot, risk_score
from .models import FormatoReporte, ReporteGenerado

DIAS_POR_PERIODO = {PeriodicidadReporte.SEMANAL: 7, PeriodicidadReporte.MENSUAL: 30}
COLOR = {"verde": (31, 138, 76), "ambar": (194, 98, 10), "rojo": (198, 40, 57)}
NIVEL = {"critical": "Crítica", "high": "Alta", "medium": "Media", "low": "Baja", "none": "Ninguna", "": "Pendiente"}


class PeriodicidadNoConfigurada(Exception):
    pass


def _datos(organization, desde, hasta):
    riesgo = risk_score(organization)
    vulns = list(
        Vulnerability.objects.filter(organization=organization)
        .exclude(status=VulnerabilityStatus.CLOSED)
        .select_related("asset")
        .order_by("-priority_score")
    )
    nuevas = Vulnerability.objects.filter(organization=organization, first_detected_at__date__gte=desde).count()
    cerradas = Vulnerability.objects.filter(organization=organization, closed_at__date__gte=desde).count()
    planes = list(RemediationPlan.objects.filter(vulnerability__organization=organization).select_related("vulnerability"))
    return {
        "riesgo": riesgo,
        "vulns": vulns,
        "nuevas": nuevas,
        "cerradas": cerradas,
        "dominios": cumplimiento_por_dominio(organization),
        "planes": planes,
        "top": principales_riesgos(organization),
        "recomendaciones": recomendaciones(organization)[:3],
    }


def _filas_vulns(d):
    return [
        [v.cve or "-", v.title[:70], v.asset.hostname if v.asset else "Pendiente de asociación",
         NIVEL.get(v.contextual_priority, v.contextual_priority), v.get_status_display(),
         "Sí" if v.is_overdue else "No"]
        for v in d["vulns"]
    ]


def _filas_planes(d):
    return [
        [p.vulnerability.title[:60], p.owner_name or "Responsable pendiente de asignación", p.due_date.isoformat(),
         p.get_status_display()]
        for p in d["planes"]
    ]


def construir_pdf(organization, desde, hasta):
    d = _datos(organization, desde, hasta)
    r = d["riesgo"]
    bloques = [
        ("titulo", f"Reporte de seguridad · {organization.name}"),
        ("parrafo", f"Periodo: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}."),
        ("subtitulo", "Resumen ejecutivo"),
        ("semaforo", COLOR[r["semaforo"]], f"Nivel de riesgo: {r['nivel'].upper()} · Risk Score {r['score']}/100"),
        ("parrafo", r["mensaje"]),
        ("parrafo",
         f"En el periodo se detectaron {d['nuevas']} hallazgos nuevos y se cerraron {d['cerradas']}. "
         f"Quedan {r['abiertas']} abiertos, de los cuales {r['graves']} son graves (alta o crítica)."),
        ("subtitulo", "Lo más importante"),
    ]
    bloques += [("parrafo", f"- {t['texto']}") for t in d["top"]] or [("parrafo", "Sin hallazgos abiertos.")]
    bloques.append(("subtitulo", "Qué se recomienda hacer"))
    bloques += [("parrafo", f"{i}. {x['accion']}") for i, x in enumerate(d["recomendaciones"], 1)] or [
        ("parrafo", "No existen controles pendientes por recomendar.")
    ]
    bloques += [
        ("salto",),
        ("subtitulo", "Vulnerabilidades abiertas"),
        ("tabla", ["CVE", "Hallazgo", "Activo", "Prioridad", "Estado", "Vencido"], _filas_vulns(d), (14, 40, 20, 10, 12, 8)),
        ("subtitulo", "Cumplimiento ISO/IEC 27001 por dominio"),
        ("tabla", ["Dominio", "Controles", "Implementados", "Parciales", "Pendientes", "% Cumplimiento"],
         [[x["tema"], x["controles"], x["implementados"], x["parciales"], x["pendientes"], f"{x['cumplimiento']} %"]
          for x in d["dominios"]], None),
        ("subtitulo", "Estado de la remediación"),
        ("tabla", ["Acción", "Responsable", "Plazo", "Estado"], _filas_planes(d), (40, 22, 12, 14)),
    ]
    return pdf_bytes("Reporte de seguridad", bloques), d


def construir_xlsx(organization, desde, hasta):
    d = _datos(organization, desde, hasta)
    r = d["riesgo"]
    resumen = [
        ["Organización", organization.name], ["Periodo", f"{desde:%d/%m/%Y} - {hasta:%d/%m/%Y}"],
        ["Risk Score", r["score"]], ["Nivel", r["nivel"]], ["Mensaje", r["mensaje"]],
        ["% cumplimiento ISO", r["cumplimiento"]], ["Hallazgos abiertos", r["abiertas"]],
        ["Graves (alta/crítica)", r["graves"]], ["Nuevos en el periodo", d["nuevas"]], ["Cerrados en el periodo", d["cerradas"]],
    ]
    hojas = [
        ("Resumen ejecutivo", ["Indicador", "Valor"], resumen),
        ("Vulnerabilidades", ["CVE", "Hallazgo", "Activo", "Prioridad", "Estado", "Vencido"], _filas_vulns(d)),
        ("Cumplimiento", ["Dominio", "Controles", "Implementados", "Parciales", "Pendientes", "% Cumplimiento"],
         [[x["tema"], x["controles"], x["implementados"], x["parciales"], x["pendientes"], x["cumplimiento"]] for x in d["dominios"]]),
        ("Remediación", ["Acción", "Responsable", "Plazo", "Estado"], _filas_planes(d)),
    ]
    return xlsx_bytes(hojas), d


def generar_reporte(organization, formato, actor, automatico=False, ahora=None):
    if not organization.periodicidad_reporte:
        raise PeriodicidadNoConfigurada("Debe configurar la periodicidad del reporte antes de continuar.")
    ahora = ahora or timezone.now()
    hasta = timezone.localtime(ahora).date()
    desde = hasta - timedelta(days=DIAS_POR_PERIODO[organization.periodicidad_reporte])
    contenido, d = (construir_pdf if formato == FormatoReporte.PDF else construir_xlsx)(organization, desde, hasta)
    reporte = ReporteGenerado(
        organization=organization,
        formato=formato,
        periodo_desde=desde,
        periodo_hasta=hasta,
        sha256_hash=hashlib.sha256(contenido).hexdigest(),
        automatico=automatico,
        generado_por=actor,
        resumen={"risk_score": d["riesgo"]["score"], "nivel": d["riesgo"]["nivel"], "abiertas": d["riesgo"]["abiertas"]},
    )
    reporte.archivo.save(f"reporte_{hasta.isoformat()}_{reporte.id.hex[:8]}.{formato}", ContentFile(contenido), save=False)
    reporte.save()
    registrar(
        organization=organization,
        actor=actor,
        accion="reporte_generado",
        modalidad=NivelAutonomia.AUTONOMO if automatico else NivelAutonomia.ASISTIDO,
        objeto_tipo="reporte",
        objeto_id=reporte.id,
        detalle={"formato": formato, "desde": str(desde), "hasta": str(hasta), "sha256": reporte.sha256_hash},
    )
    return reporte


def reporte_vencido(organization, ahora):
    if not organization.periodicidad_reporte:
        return False
    if organization.ultimo_reporte_en is None:
        return True
    return ahora - organization.ultimo_reporte_en >= timedelta(days=DIAS_POR_PERIODO[organization.periodicidad_reporte])


def generar_reportes_periodicos(ahora=None):
    """Tarea programada: para cada organización con periodicidad vencida genera PDF y Excel y avisa."""
    ahora = ahora or timezone.now()
    generados = []
    for org in Organization.objects.exclude(periodicidad_reporte=""):
        if not reporte_vencido(org, ahora):
            continue
        registrar_snapshot(org)
        pdf = generar_reporte(org, FormatoReporte.PDF, "agente", automatico=True, ahora=ahora)
        xlsx = generar_reporte(org, FormatoReporte.XLSX, "agente", automatico=True, ahora=ahora)
        org.ultimo_reporte_en = ahora
        org.save(update_fields=["ultimo_reporte_en"])
        notificar(
            organization=org,
            tipo=TipoNotificacion.REPORTE,
            titulo=f"Reporte {org.get_periodicidad_reporte_display().lower()} disponible",
            mensaje="El agente generó el reporte de seguridad del periodo en PDF y Excel.",
            enlace="/reportes",
            roles=("admin", "compliance", "it_owner"),
            objeto_tipo="reporte",
            objeto_id=pdf.id,
        )
        generados += [pdf, xlsx]
    return generados
