"""
HU28: acceso por rol a cada módulo de la consola.

Cada vista de la API declara a qué módulo pertenece (atributo `modulo`)
y el permiso por defecto (common.permissions) rechaza con 403 "Permisos
insuficientes" si el rol del usuario no tiene ese módulo. El frontend
recibe la misma lista en /api/auth/me/ (campo `modulos`) para mostrar
solo el menú que corresponde; pero la regla que manda es la del backend.

Roles del backlog -> roles del sistema:
  Gerencia ................ admin (Administrador)
  TI ...................... it_owner (Responsable de TI)
  Cumplimiento ............ compliance (Oficial de Cumplimiento)
  Personal administrativo . staff (Personal administrativo / clínico)
Además: analyst (Analista de seguridad) y auditor (solo lectura de todo).
"""

from accounts.models import Role

MODULOS = {
    "panel": "Panel general",
    "ejecutivo": "Cuadro de mando ejecutivo",
    "vulnerabilidades": "Vulnerabilidades e historial",
    "riesgos": "Matriz de riesgos",
    "remediacion": "Plan de corrección y verificación",
    "controles": "Controles ISO 27001",
    "evidencias": "Evidencias",
    "activos": "Activos",
    "gobernanza": "Aprobaciones, autonomía y acciones del agente",
    "auditoria": "Registro de auditoría",
    "incidentes": "Reporte de incidentes",
    "asistente": "Asistente (preguntas en lenguaje natural)",
    "informes": "Reportes",
    "integraciones": "Fuentes de datos y CVE",
    "configuracion": "Configuración",
    "notificaciones": "Notificaciones",
}

TODOS = set(MODULOS)

ACCESO_POR_ROL = {
    Role.ADMIN: TODOS,
    Role.AUDITOR: TODOS,  # ve todo, pero no escribe (common.permissions)
    Role.IT_OWNER: TODOS - {"ejecutivo"},
    Role.ANALYST: {
        "panel", "vulnerabilidades", "riesgos", "remediacion", "controles", "evidencias", "activos",
        "gobernanza", "auditoria", "incidentes", "asistente", "informes", "integraciones",
        "configuracion", "notificaciones",
    },
    Role.COMPLIANCE: {
        "panel", "ejecutivo", "vulnerabilidades", "riesgos", "remediacion", "controles", "evidencias",
        "gobernanza", "auditoria", "incidentes", "asistente", "informes", "configuracion", "notificaciones",
    },
    Role.STAFF: {"incidentes", "configuracion", "notificaciones"},
}


def modulos_de(rol):
    return sorted(ACCESO_POR_ROL.get(rol, set()))


def puede(rol, modulo):
    return modulo in ACCESO_POR_ROL.get(rol, set())
