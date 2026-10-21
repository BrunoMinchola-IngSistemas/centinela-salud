"""
Catálogo de controles ISO/IEC 27001:2022 (Anexo A) seleccionados para
una PyME de salud, y tabla de mapeo hallazgo -> control (HU11).

Por qué no son los 93 controles
-------------------------------
El Anexo A tiene 93 controles en 4 temas (Organizacionales 5.x,
Personas 6.x, Físicos 7.x, Tecnológicos 8.x). Para el alcance de esta
tesis (un agente que detecta vulnerabilidades técnicas en una clínica
pequeña) se incluyen:

1. Todos los controles que aparecen en la tabla de mapeo hallazgo ->
   control del documento OE2 (sección 8.5), porque son los que el
   agente puede evidenciar con datos reales de OpenVAS/Wazuh.
2. Unos pocos controles adicionales que ISO 27799:2016 (guía de
   seguridad de la información para el sector salud, basada en
   ISO/IEC 27002) destaca para organizaciones de salud: copias de
   seguridad (ransomware en clínicas), segmentación de la red de
   equipos biomédicos, continuidad de servicios clínicos,
   concienciación del personal y uso de servicios en la nube (el
   despliegue elegido en el benchmarking es AWS).

Los controles físicos (7.x) y la mayoría de los organizacionales de
gobierno no se incluyen porque el agente no tiene cómo observarlos
automáticamente; se evalúan con el proceso manual del Oficial de
Cumplimiento, fuera del sistema.

Nota sobre ISO 27799: su edición vigente (2016) está alineada con la
numeración de ISO/IEC 27002:2013, no con la de 2022, así que el campo
`health_rationale` es una referencia temática (qué recomienda la guía
de salud sobre ese tema), no una equivalencia código a código.
"""

# Temas del Anexo A (HU13: % de cumplimiento por tema).
TEMAS = {
    "5": ("organizacional", "Organizacionales"),
    "6": ("personas", "Personas"),
    "7": ("fisico", "Físicos"),
    "8": ("tecnologico", "Tecnológicos"),
}

# (código, nombre, puntaje base, por qué importa en salud, códigos HIPAA/CIS si se conocen)
CONTROLES = [
    ("5.7", "Inteligencia de amenazas", 65,
     "Permite saber a tiempo si una CVE que afecta a equipos clínicos se está explotando (CISA KEV, alertas del sector salud).", {}),
    ("5.9", "Inventario de información y otros activos asociados", 70,
     "ISO 27799 exige identificar qué sistemas contienen información de salud; un equipo no inventariado es un riesgo invisible.", {"cis": "CIS 1"}),
    ("5.15", "Control de acceso", 79,
     "El acceso a la historia clínica debe limitarse por función (médico, admisión, laboratorio).", {"hipaa": "§164.312(a)(1)", "cis": "CIS 6"}),
    ("5.17", "Información de autenticación", 66,
     "Credenciales por defecto en dispositivos médicos y cuentas compartidas son un hallazgo frecuente en clínicas.", {}),
    ("5.18", "Derechos de acceso", 72,
     "Revisar y retirar accesos de personal rotativo (residentes, practicantes, terceros).", {}),
    ("5.23", "Seguridad de la información para el uso de servicios en la nube", 68,
     "El despliegue elegido es AWS: responsabilidad compartida, cifrado y ubicación de los datos clínicos.", {}),
    ("5.24", "Planificación y preparación de la gestión de incidentes", 62,
     "La clínica debe saber qué hacer ante un incidente antes de que ocurra (roles, contactos, escalamiento).", {}),
    ("5.25", "Evaluación y decisión sobre eventos de seguridad", 70,
     "Distinguir una alerta menor de un incidente que afecta la atención de pacientes.", {}),
    ("5.26", "Respuesta a incidentes de seguridad", 66,
     "Responder de forma documentada y con evidencia; requisito para justificar ante la autoridad (Ley 29733).", {}),
    ("5.30", "Preparación de las TIC para la continuidad del negocio", 64,
     "ISO 27799 prioriza la disponibilidad: si cae el sistema clínico, se afecta la atención de pacientes.", {}),
    ("5.34", "Privacidad y protección de la información de identificación personal", 74,
     "La historia clínica es dato sensible según la Ley N.° 29733; es el núcleo de ISO 27799.", {}),
    ("6.3", "Concienciación, educación y formación en seguridad", 60,
     "El personal clínico es el primer vector de phishing; ISO 27799 recomienda formación periódica.", {}),
    ("6.8", "Reporte de eventos de seguridad de la información", 63,
     "Que cualquier persona del personal pueda reportar algo sospechoso en segundos (HU30).", {}),
    ("8.1", "Dispositivos de punto final de usuario", 69,
     "Estaciones de admisión y laboratorio con sistemas antiguos (p. ej. Windows 7).", {}),
    ("8.2", "Derechos de acceso privilegiado", 71,
     "Las cuentas de administrador del dominio y de los sistemas clínicos deben ser pocas y controladas.", {}),
    ("8.5", "Autenticación segura", 68,
     "Segundo factor para accesos remotos e historias clínicas.", {"hipaa": "§164.312(d)", "cis": "CIS 5"}),
    ("8.7", "Protección contra malware", 85,
     "El ransomware es la amenaza más frecuente contra hospitales y clínicas.", {"hipaa": "§164.308(a)(5)(ii)(B)", "cis": "CIS 10"}),
    ("8.8", "Gestión de vulnerabilidades técnicas", 82,
     "Control central del agente: detectar, priorizar y corregir vulnerabilidades.", {"hipaa": "§164.308(a)(1)(ii)(A)", "cis": "CIS 7"}),
    ("8.9", "Gestión de la configuración", 74,
     "Configuraciones seguras y homogéneas en servidores y equipos clínicos.", {"hipaa": "§164.308(a)(8)", "cis": "CIS 4"}),
    ("8.11", "Enmascaramiento de datos", 65,
     "Seudonimizar datos de pacientes en entornos de prueba y reportes (caso de estudio 'SaludMedica').", {}),
    ("8.13", "Copias de seguridad de la información", 73,
     "Respaldos probados y aislados: la diferencia entre recuperarse o pagar un rescate.", {"cis": "CIS 11"}),
    ("8.15", "Registro (logging)", 88,
     "Registrar quién accedió a qué historia clínica y cuándo.", {"hipaa": "§164.312(b)", "cis": "CIS 8"}),
    ("8.16", "Actividades de monitoreo", 76,
     "Monitoreo continuo con Wazuh para detectar actividad anómala.", {}),
    ("8.19", "Instalación de software en sistemas operativos", 70,
     "Evitar software no autorizado o desactualizado en equipos clínicos.", {}),
    ("8.20", "Seguridad de redes", 72,
     "Proteger la red donde viajan imágenes diagnósticas y resultados de laboratorio.", {}),
    ("8.22", "Segregación de redes", 72,
     "Separar dispositivos biomédicos (bombas de infusión, equipos de imágenes) del resto de la red.", {"hipaa": "§164.308(a)(4)", "cis": "CIS 12"}),
    ("8.24", "Uso de criptografía", 77,
     "Cifrado en tránsito (portal de pacientes) y en reposo (historias clínicas).", {"hipaa": "§164.312(e)(1)", "cis": "CIS 3"}),
    ("8.26", "Requisitos de seguridad de las aplicaciones", 67,
     "El portal de pacientes y el sistema de citas están expuestos a Internet.", {}),
    ("8.28", "Codificación segura", 66,
     "Aplica a desarrollos propios o encargados a terceros (portal, integraciones).", {}),
    ("8.29", "Pruebas de seguridad en desarrollo y aceptación", 64,
     "Probar la seguridad antes de poner en producción cambios en sistemas clínicos.", {}),
    ("8.32", "Gestión de cambios", 70,
     "Un parche mal aplicado puede detener un servicio clínico; los cambios deben planificarse y poder revertirse.", {}),
]


class CategoriaHallazgo:
    """Categorías de la tabla de mapeo de la sección 8.5 del OE2."""

    SOFTWARE_DESACTUALIZADO = "software_desactualizado"
    CONFIG_INSEGURA = "config_insegura"
    FALLA_APP_WEB = "falla_app_web"
    PRIVILEGIOS_EXCESIVOS = "privilegios_excesivos"
    AUTENTICACION_DEBIL = "autenticacion_debil"
    ACTIVO_NO_INVENTARIADO = "activo_no_inventariado"
    SIN_REGISTROS = "sin_registros"
    DATOS_CLINICOS_EXPUESTOS = "datos_clinicos_expuestos"
    MALWARE = "malware"
    INCIDENTE_PERSONAL = "incidente_personal"
    NUEVA_VULNERABILIDAD = "nueva_vulnerabilidad"

    CHOICES = [
        (SOFTWARE_DESACTUALIZADO, "Software desactualizado o sin parche"),
        (CONFIG_INSEGURA, "Configuración insegura / protocolos obsoletos"),
        (FALLA_APP_WEB, "Fallas en aplicaciones web"),
        (PRIVILEGIOS_EXCESIVOS, "Privilegios excesivos o cuentas inactivas"),
        (AUTENTICACION_DEBIL, "Autenticación débil / sin segundo factor"),
        (ACTIVO_NO_INVENTARIADO, "Activo no inventariado (shadow IT)"),
        (SIN_REGISTROS, "Ausencia de registros o monitoreo"),
        (DATOS_CLINICOS_EXPUESTOS, "Datos clínicos expuestos o sin cifrar"),
        (MALWARE, "Malware o actividad maliciosa"),
        (INCIDENTE_PERSONAL, "Incidente reportado por el personal"),
        (NUEVA_VULNERABILIDAD, "Nueva vulnerabilidad que afecta un activo"),
    ]


# Tabla de la sección 8.5, tal cual el documento.
MAPEO_CATEGORIA_A_CONTROLES = {
    CategoriaHallazgo.SOFTWARE_DESACTUALIZADO: ["8.8", "8.19", "8.32"],
    CategoriaHallazgo.CONFIG_INSEGURA: ["8.9", "8.20", "8.24"],
    CategoriaHallazgo.FALLA_APP_WEB: ["8.26", "8.28", "8.29"],
    CategoriaHallazgo.PRIVILEGIOS_EXCESIVOS: ["5.15", "5.18", "8.2"],
    CategoriaHallazgo.AUTENTICACION_DEBIL: ["5.17", "8.5"],
    CategoriaHallazgo.ACTIVO_NO_INVENTARIADO: ["5.9", "8.1"],
    CategoriaHallazgo.SIN_REGISTROS: ["8.15", "8.16"],
    CategoriaHallazgo.DATOS_CLINICOS_EXPUESTOS: ["5.34", "8.11", "8.24"],
    CategoriaHallazgo.MALWARE: ["8.7", "5.25"],
    CategoriaHallazgo.INCIDENTE_PERSONAL: ["6.8", "5.26"],
    CategoriaHallazgo.NUEVA_VULNERABILIDAD: ["5.7", "8.8"],
}


def tema_de(codigo_iso):
    return TEMAS.get(codigo_iso.split(".")[0], ("", ""))[0]
