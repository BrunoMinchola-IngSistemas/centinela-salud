"""
Dominio "Gobernanza de la remediación y autonomía" del documento OE2
(sección 8.4 del Resumen de Contexto): niveles de autonomía, solicitudes
de aprobación para acciones de alto impacto y el registro de auditoría
de solo inserción (HU23, HU24, HU27).
"""

import uuid

from django.db import models

from accounts.models import Organization
from remediation.models import RemediationPlan


class NivelAutonomia(models.TextChoices):
    """
    HU23: tres niveles, tal como los define la sección 8.4 del
    documento de contexto. No son solo una etiqueta: el nivel decide si
    remediation.views ejecuta la acción sola, solo la recomienda, o
    exige una SolicitudAprobacion antes de tocar nada.
    """

    AUTONOMO = "autonomo", "Autónomo (lista blanca)"
    ASISTIDO = "asistido", "Asistido (el agente recomienda, TI ejecuta)"
    CON_APROBACION = "con_aprobacion", "Con aprobación gerencial"


class TipoAccion(models.TextChoices):
    """Catálogo mínimo de tipos de acción que puede tomar el agente (HU18, HU23)."""

    NOTIFICAR = "notificar", "Notificar"
    ABRIR_TICKET = "abrir_ticket", "Abrir ticket"
    DESACTIVAR_CUENTA = "desactivar_cuenta", "Desactivar cuenta inactiva"
    APLICAR_PARCHE = "aplicar_parche", "Aplicar parche"
    MODIFICAR_CONFIG = "modificar_config", "Modificar configuración"
    AISLAR_SERVIDOR = "aislar_servidor", "Aislar servidor de producción"
    OTRO = "otro", "Otro"


# Lista blanca inicial (HU18): qué tipos de acción puede ejecutar el
# agente sin pedir nada a nadie. Se deja como constante (no como tabla)
# porque el propio documento (sección 15, bloque 4) la trata como un
# parámetro a decidir con los asesores, no como dato de usuario final;
# cambiarla es un cambio de política, no una operación de la consola.
ACCIONES_AUTONOMAS_LISTA_BLANCA = {
    TipoAccion.NOTIFICAR,
    TipoAccion.ABRIR_TICKET,
    TipoAccion.DESACTIVAR_CUENTA,
}

# Mapa nivel de autonomía -> tipos de acción que le corresponden, según
# la tabla de la sección 8.4. Usado para decidir qué nivel se asigna a
# una PoliticaAutonomia nueva, y como referencia en la UI/documentación.
NIVEL_POR_TIPO_ACCION = {
    TipoAccion.NOTIFICAR: NivelAutonomia.AUTONOMO,
    TipoAccion.ABRIR_TICKET: NivelAutonomia.AUTONOMO,
    TipoAccion.DESACTIVAR_CUENTA: NivelAutonomia.AUTONOMO,
    TipoAccion.APLICAR_PARCHE: NivelAutonomia.ASISTIDO,
    TipoAccion.MODIFICAR_CONFIG: NivelAutonomia.ASISTIDO,
    TipoAccion.AISLAR_SERVIDOR: NivelAutonomia.CON_APROBACION,
    TipoAccion.OTRO: NivelAutonomia.ASISTIDO,
}


class PoliticaAutonomia(models.Model):
    """
    Qué nivel de autonomía aplica a un tipo de acción, por organización.
    Se siembra con NIVEL_POR_TIPO_ACCION pero cada organización puede
    ajustarlo (p. ej. una clínica más conservadora puede subir
    "aplicar_parche" a "con_aprobacion").
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="politicas_autonomia")
    tipo_accion = models.CharField(max_length=30, choices=TipoAccion.choices)
    nivel = models.CharField(max_length=20, choices=NivelAutonomia.choices)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "tipo_accion")
        ordering = ["tipo_accion"]
        verbose_name = "Política de autonomía"
        verbose_name_plural = "Políticas de autonomía"

    def __str__(self):
        return f"{self.get_tipo_accion_display()} → {self.get_nivel_display()}"


class EstadoSolicitud(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"
    ESCALADA = "escalada", "Escalada"


class SolicitudAprobacion(models.Model):
    """
    HU24: una acción de alto impacto no se ejecuta sola. El agente
    arma esta solicitud con el riesgo de NO actuar y el efecto
    esperado SI se actúa, para que el Gerente General decida con
    contexto, no a ciegas. Si no hay respuesta en el plazo, se escala
    a un segundo responsable (campo escalado_a).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(RemediationPlan, on_delete=models.CASCADE, related_name="solicitudes_aprobacion")
    tipo_accion = models.CharField(max_length=30, choices=TipoAccion.choices)
    riesgo_de_no_actuar = models.TextField(help_text="Qué puede pasar si esta acción NO se ejecuta.")
    efecto_esperado = models.TextField(help_text="Qué cambia en el sistema si esta acción SÍ se ejecuta.")
    estado = models.CharField(max_length=20, choices=EstadoSolicitud.choices, default=EstadoSolicitud.PENDIENTE)
    solicitado_en = models.DateTimeField(auto_now_add=True)
    plazo = models.DateTimeField(help_text="Si no hay respuesta para esta fecha, se escala.")
    decidido_por = models.CharField(max_length=150, blank=True)
    decidido_en = models.DateTimeField(null=True, blank=True)
    comentario_decision = models.TextField(blank=True)
    escalado_a = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-solicitado_en"]
        verbose_name = "Solicitud de aprobación"
        verbose_name_plural = "Solicitudes de aprobación"

    def __str__(self):
        return f"Solicitud {self.id} · {self.get_tipo_accion_display()} · {self.get_estado_display()}"


class RegistroAuditoria(models.Model):
    """
    HU27 / RNF-05: "log no editable ni borrable". Se modela como una
    tabla de SOLO INSERCIÓN: el ViewSet (ver views.py) no expone
    update/partial_update/destroy, y en PostgreSQL se recomienda además
    revocar UPDATE/DELETE a nivel de rol de base de datos (ver
    docs/auditoria_postgresql.sql, pendiente de aplicar al migrar de
    SQLite a Postgres).

    No se usa un ForeignKey "genérico" (GenericForeignKey) a propósito:
    para un log de auditoría interesa poder leerlo sin tener que unir
    con la tabla de cada tipo de objeto, así que se guarda el tipo y el
    id como texto plano más una copia de los datos relevantes en
    `detalle` (JSON), que es lo que de verdad hace falta para explicar
    "qué pasó" sin ir a buscarlo en otro lado.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="registros_auditoria")
    actor = models.CharField(max_length=150, help_text="Usuario humano, o 'agente' si decidió el sistema.")
    accion = models.CharField(max_length=100, help_text="Ej: 'verificacion_cerrada', 'solicitud_aprobada'.")
    modalidad = models.CharField(
        max_length=20,
        choices=NivelAutonomia.choices,
        help_text="Bajo qué nivel de autonomía ocurrió esta acción.",
    )
    objeto_tipo = models.CharField(max_length=50, help_text="Ej: 'vulnerability', 'remediation_plan'.")
    objeto_id = models.CharField(max_length=64)
    detalle = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"
        indexes = [models.Index(fields=["organization", "objeto_tipo", "objeto_id"])]

    def __str__(self):
        return f"[{self.creado_en}] {self.actor} · {self.accion}"

    def save(self, *args, **kwargs):
        # No editable ni borrable: una vez creado (pk ya asignado por
        # el UUIDField con default), cualquier intento de volver a
        # guardar el mismo registro se rechaza. Esto es la mitad
        # aplicativa de RNF-05; la otra mitad (permisos a nivel de
        # motor de BD) va en el script de Postgres mencionado arriba.
        if self.pk and RegistroAuditoria.objects.filter(pk=self.pk).exists():
            raise ValueError("RegistroAuditoria es de solo inserción: no se puede modificar un registro existente.")
        super().save(*args, **kwargs)
