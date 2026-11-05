"""Punto único para avisar a las personas (igual que governance.audit.registrar para la auditoría)."""

import logging

from django.core.mail import send_mail

from accounts.models import Role
from accounts.models import User as Perfil

from .models import NivelNotificacion, Notificacion

logger = logging.getLogger(__name__)

# Quién recibe cada aviso por defecto: el Responsable de TI y la Gerencia.
ROLES_TI = (Role.IT_OWNER, Role.ADMIN)


def destinatarios(organization, roles=ROLES_TI):
    return [
        p.user
        for p in Perfil.objects.select_related("user").filter(organization=organization, role__in=roles, user__is_active=True)
    ]


def notificar(
    *,
    organization,
    tipo,
    titulo,
    mensaje="",
    nivel=NivelNotificacion.INFO,
    enlace="",
    roles=ROLES_TI,
    usuarios=None,
    objeto_tipo="",
    objeto_id="",
    enviar_email=True,
):
    """
    Crea una notificación por destinatario (los usuarios indicados, o
    todos los activos de la organización con alguno de `roles`) y, si
    tienen correo, intenta mandarla por email. Un fallo de correo nunca
    rompe el flujo que generó el aviso.
    """
    personas = usuarios if usuarios is not None else destinatarios(organization, roles)
    creadas = []
    vistos = set()
    for user in personas:
        if user is None or user.pk in vistos:
            continue
        vistos.add(user.pk)
        n = Notificacion.objects.create(
            organization=organization,
            destinatario=user,
            tipo=tipo,
            nivel=nivel,
            titulo=titulo[:200],
            mensaje=mensaje,
            enlace=enlace,
            objeto_tipo=objeto_tipo,
            objeto_id=str(objeto_id or ""),
        )
        if enviar_email and user.email:
            try:
                send_mail(
                    subject=f"[Centinela Salud] {titulo}"[:150],
                    message=f"{mensaje}\n\nRevísalo en la consola: {enlace or '/'}",
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                n.email_enviado = True
                n.save(update_fields=["email_enviado"])
            except Exception:  # noqa: BLE001 - el aviso en la consola ya quedó creado
                logger.warning("No se pudo enviar el correo de la notificación %s", n.id, exc_info=True)
        creadas.append(n)
    return creadas
