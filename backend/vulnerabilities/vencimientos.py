"""
HU22: cuando una vulnerabilidad crítica supera su plazo de remediación,
el agente avisa a TI y a la Gerencia (consola + correo) y el tablero la
muestra como "vencida". Se avisa una sola vez por hallazgo.
"""

from django.db.models import Q
from django.utils import timezone

from governance.audit import registrar
from governance.models import NivelAutonomia

from .models import Vulnerability, VulnerabilityStatus


def criticas_vencidas(hoy=None):
    hoy = hoy or timezone.localdate()
    return (
        Vulnerability.objects.exclude(status=VulnerabilityStatus.CLOSED)
        .filter(Q(contextual_priority="critical") | Q(severity="critical"))
        .filter(Q(due_date__lt=hoy) | Q(due_date__isnull=True, plan__due_date__lt=hoy))
        .select_related("asset", "plan", "organization")
    )


def revisar_vencimientos(hoy=None):
    from notificaciones.models import NivelNotificacion, TipoNotificacion
    from notificaciones.servicios import notificar

    avisadas = []
    for v in criticas_vencidas(hoy).filter(vencimiento_notificado_en__isnull=True):
        limite = v.fecha_limite
        equipo = v.asset.hostname if v.asset else "activo pendiente de asociación"
        notificar(
            organization=v.organization,
            tipo=TipoNotificacion.VENCIMIENTO,
            nivel=NivelNotificacion.CRITICA,
            titulo=f"Vulnerabilidad crítica vencida: {v.title}",
            mensaje=f"El plazo de remediación venció el {limite:%d/%m/%Y} y sigue abierta en {equipo}. Responsable: "
            f"{getattr(getattr(v, 'plan', None), 'owner_name', '') or 'sin asignar'}.",
            enlace="/vulnerabilidades",
            objeto_tipo="vulnerability",
            objeto_id=v.id,
        )
        v.vencimiento_notificado_en = timezone.now()
        v.save(update_fields=["vencimiento_notificado_en"])
        registrar(
            organization=v.organization,
            actor="agente",
            accion="vencimiento_notificado",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id=v.id,
            detalle={"hallazgo": v.title, "plazo": str(limite)},
        )
        avisadas.append(v)
    return avisadas
