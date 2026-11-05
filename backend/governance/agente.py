"""
Motor de decisión del agente (HU18, HU23, HU24).

`proponer_accion(plan, tipo_accion, ...)` aplica la política de
autonomía de la organización y deja registrado el resultado:

  nivel autónomo + lista blanca + interruptor encendido -> ejecuta (HU18 esc. 1)
  nivel autónomo + interruptor apagado                   -> pendiente manual (HU18 esc. 2)
  nivel asistido                                         -> pendiente manual (TI ejecuta)
  nivel con aprobación                                   -> SolicitudAprobacion; no se ejecuta
                                                            hasta que la Gerencia apruebe (HU23/HU24)

`escalar_vencidas()` (tarea programada) escala las solicitudes sin
respuesta dentro del plazo a un segundo responsable (HU24 esc. 2).
"""

from datetime import timedelta

from django.utils import timezone

from accounts.models import Role
from accounts.models import User as Perfil
from notificaciones.models import NivelNotificacion, TipoNotificacion
from notificaciones.servicios import notificar

from .audit import registrar
from .models import (
    ACCIONES_AUTONOMAS_LISTA_BLANCA,
    NIVEL_POR_TIPO_ACCION,
    AccionAgente,
    EstadoAccion,
    EstadoSolicitud,
    NivelAutonomia,
    PoliticaAutonomia,
    SolicitudAprobacion,
    TipoAccion,
)

PLAZO_APROBACION = timedelta(hours=48)

RIESGO_POR_TIPO = {
    TipoAccion.AISLAR_SERVIDOR: (
        "Si no se aísla, un atacante podría seguir moviéndose desde este servidor hacia el resto de la red clínica.",
        "El servidor queda fuera de la red mientras se corrige: los servicios que dependen de él no estarán disponibles.",
    ),
    TipoAccion.APLICAR_PARCHE: (
        "Si no se parcha, la vulnerabilidad sigue explotable.",
        "Se instala la actualización; puede requerir reinicio del equipo.",
    ),
    TipoAccion.MODIFICAR_CONFIG: (
        "Si no se corrige la configuración, el equipo sigue expuesto.",
        "Se cambia la configuración insegura por la recomendada.",
    ),
}


def nivel_para(organization, tipo_accion):
    politica = PoliticaAutonomia.objects.filter(organization=organization, tipo_accion=tipo_accion).first()
    return politica.nivel if politica else NIVEL_POR_TIPO_ACCION.get(tipo_accion, NivelAutonomia.ASISTIDO)


def _ejecutar(accion, actor, modalidad):
    """Ejecutores simulados: registran qué haría el agente, sin tocar sistemas reales."""
    plan = accion.plan
    vuln = plan.vulnerability
    org = accion.organization
    equipo = vuln.asset.hostname if vuln.asset else "activo pendiente de asociación"
    if accion.tipo_accion == TipoAccion.NOTIFICAR:
        notificar(
            organization=org,
            tipo=TipoNotificacion.ACCION_AGENTE,
            titulo=f"Acción requerida: {vuln.title}",
            mensaje=f"El agente asignó la corrección de «{vuln.title}» en {equipo}. Plazo: {plan.due_date:%d/%m/%Y}.",
            enlace="/plan",
            objeto_tipo="remediation_plan",
            objeto_id=plan.id,
        )
        resultado = "Notificación enviada a TI (consola y correo si está configurado)."
    elif accion.tipo_accion == TipoAccion.ABRIR_TICKET:
        numero = f"CS-{timezone.now():%Y%m%d}-{str(accion.id)[:6].upper()}"
        plan.notes = (plan.notes + "\n" if plan.notes else "") + f"Ticket interno {numero} abierto por el agente."
        plan.save(update_fields=["notes"])
        resultado = f"Ticket interno {numero} abierto y anotado en el plan."
    elif accion.tipo_accion == TipoAccion.DESACTIVAR_CUENTA:
        resultado = f"[Simulación] Se desactivaría la cuenta inactiva señalada en «{vuln.title}» (sin conector a Active Directory)."
    else:
        resultado = f"[Simulación] Se ejecutaría «{accion.get_tipo_accion_display()}» sobre {equipo} (sin conector a la infraestructura de la clínica)."
    accion.estado = EstadoAccion.EJECUTADA
    accion.ejecutada_por = actor
    accion.ejecutado_en = timezone.now()
    accion.resultado = resultado
    accion.save(update_fields=["estado", "ejecutada_por", "ejecutado_en", "resultado"])
    registrar(
        organization=org,
        actor=actor,
        accion="accion_ejecutada",
        modalidad=modalidad,
        objeto_tipo="remediation_plan",
        objeto_id=plan.id,
        detalle={
            "accion_id": str(accion.id),
            "tipo_accion": accion.tipo_accion,
            "hallazgo": vuln.title,
            "autonoma": modalidad == NivelAutonomia.AUTONOMO,
            "resultado": resultado,
        },
    )
    return accion


def proponer_accion(plan, tipo_accion, propuesta_por="agente", detalle=""):
    org = plan.vulnerability.organization
    nivel = nivel_para(org, tipo_accion)
    accion = AccionAgente.objects.create(
        organization=org, plan=plan, tipo_accion=tipo_accion, nivel_aplicado=nivel,
        estado=EstadoAccion.PENDIENTE_MANUAL, propuesta_por=propuesta_por, detalle=detalle,
    )

    if nivel == NivelAutonomia.AUTONOMO and tipo_accion in ACCIONES_AUTONOMAS_LISTA_BLANCA:
        if org.ejecucion_autonoma_activa:
            accion.motivo = "Acción de bajo riesgo en la lista blanca y ejecución autónoma activada."
            accion.save(update_fields=["motivo"])
            return _ejecutar(accion, "agente", NivelAutonomia.AUTONOMO)
        accion.motivo = "La ejecución autónoma está desactivada: queda pendiente de aprobación manual de TI."
    elif nivel == NivelAutonomia.CON_APROBACION:
        riesgo, efecto = RIESGO_POR_TIPO.get(
            tipo_accion, ("Si no se actúa, el hallazgo sigue abierto.", "Se ejecuta la acción propuesta.")
        )
        solicitud = SolicitudAprobacion.objects.create(
            plan=plan, tipo_accion=tipo_accion, riesgo_de_no_actuar=riesgo, efecto_esperado=efecto,
            plazo=timezone.now() + PLAZO_APROBACION,
        )
        accion.estado = EstadoAccion.PENDIENTE_APROBACION
        accion.solicitud = solicitud
        accion.motivo = "Acción de alto impacto: bloqueada hasta contar con aprobación explícita de la Gerencia."
        avisar_solicitud(solicitud)
    else:
        accion.motivo = "Nivel asistido: el agente recomienda y TI ejecuta."
    accion.save(update_fields=["estado", "solicitud", "motivo"])
    registrar(
        organization=org,
        actor=propuesta_por,
        accion="accion_propuesta",
        modalidad=nivel,
        objeto_tipo="remediation_plan",
        objeto_id=plan.id,
        detalle={"accion_id": str(accion.id), "tipo_accion": tipo_accion, "estado": accion.estado, "motivo": accion.motivo},
    )
    return accion


def ejecutar_manual(accion, actor):
    if accion.estado != EstadoAccion.PENDIENTE_MANUAL:
        raise ValueError("Solo se puede ejecutar a mano una acción pendiente de ejecución manual.")
    return _ejecutar(accion, actor, NivelAutonomia.ASISTIDO)


def resolver_solicitud(solicitud, aprobada, actor):
    """Al decidir una solicitud, la acción que estaba bloqueada se ejecuta o se rechaza."""
    for accion in solicitud.acciones.filter(estado=EstadoAccion.PENDIENTE_APROBACION):
        if aprobada:
            _ejecutar(accion, actor, NivelAutonomia.CON_APROBACION)
        else:
            accion.estado = EstadoAccion.RECHAZADA
            accion.motivo = f"Rechazada por {actor}."
            accion.save(update_fields=["estado", "motivo"])


def avisar_solicitud(solicitud):
    vuln = solicitud.plan.vulnerability
    notificar(
        organization=vuln.organization,
        tipo=TipoNotificacion.APROBACION,
        nivel=NivelNotificacion.ADVERTENCIA,
        titulo=f"Aprobación requerida: {solicitud.get_tipo_accion_display()}",
        mensaje=(
            f"Hallazgo: {vuln.title}. Riesgo de no actuar: {solicitud.riesgo_de_no_actuar} "
            f"Efecto esperado: {solicitud.efecto_esperado} Plazo: {timezone.localtime(solicitud.plazo):%d/%m/%Y %H:%M}."
        ),
        enlace="/gobernanza",
        roles=(Role.ADMIN,),
        objeto_tipo="solicitud",
        objeto_id=solicitud.id,
    )


def segundo_responsable(organization):
    if organization.responsable_escalamiento_id:
        return organization.responsable_escalamiento
    perfil = (
        Perfil.objects.select_related("user")
        .filter(organization=organization, role=Role.IT_OWNER, user__is_active=True)
        .order_by("user__username")
        .first()
    )
    return perfil.user if perfil else None


def escalar_vencidas(ahora=None):
    """HU24 esc. 2: solicitudes pendientes cuyo plazo venció -> escaladas al segundo responsable."""
    ahora = ahora or timezone.now()
    escaladas = []
    for s in SolicitudAprobacion.objects.select_related("plan__vulnerability__organization").filter(
        estado=EstadoSolicitud.PENDIENTE, plazo__lt=ahora
    ):
        org = s.plan.vulnerability.organization
        destino = segundo_responsable(org)
        s.estado = EstadoSolicitud.ESCALADA
        s.escalado_a = destino.username if destino else "sin segundo responsable configurado"
        s.save(update_fields=["estado", "escalado_a"])
        registrar(
            organization=org,
            actor="agente",
            accion="solicitud_escalada",
            modalidad=NivelAutonomia.CON_APROBACION,
            objeto_tipo="remediation_plan",
            objeto_id=s.plan_id,
            detalle={"solicitud_id": str(s.id), "escalado_a": s.escalado_a, "plazo": s.plazo.isoformat()},
        )
        notificar(
            organization=org,
            tipo=TipoNotificacion.ESCALAMIENTO,
            nivel=NivelNotificacion.CRITICA,
            titulo=f"Solicitud escalada sin respuesta: {s.get_tipo_accion_display()}",
            mensaje=f"Nadie respondió antes del plazo. Hallazgo: {s.plan.vulnerability.title}. Se escaló a {s.escalado_a}.",
            enlace="/gobernanza",
            usuarios=[u for u in [destino] if u] + [p.user for p in Perfil.objects.filter(organization=org, role=Role.ADMIN)],
            objeto_tipo="solicitud",
            objeto_id=s.id,
        )
        escaladas.append(s)
    return escaladas
