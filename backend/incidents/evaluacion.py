"""
HU30: el agente evalúa el reporte del personal en el momento.

Clasificación por reglas en español (palabras clave del texto libre),
pensada para reportes de personal no técnico: "me llegó un correo
pidiendo mi clave", "la computadora muestra un mensaje de rescate",
"se perdió la laptop de admisión". Devuelve categoría, severidad, un
resumen y qué debe hacer TI primero. Es determinista y explicable (dice
qué palabras la activaron); si luego se conecta Qwen, puede refinarla.
"""

import re
import unicodedata

from .models import CategoriaIncidente

REGLAS = [
    (CategoriaIncidente.MALWARE, r"ransom|rescate|cifrad|encriptad|virus|malware|troyano|antivirus|archivos? (raros|extran)|ventana emergente|pantalla (roja|bloqueada)"),
    (CategoriaIncidente.FUGA, r"historia(s)? clinica|datos? de(l)? paciente|usb|pendrive|filtr|envi(e|o|aron) (datos|informacion)|fotocopi|publicad"),
    (CategoriaIncidente.PHISHING, r"correo|e-?mail|enlace|link|adjunto|phishing|whatsapp|sms|mensaje|premio|banco|verificar (su|tu) cuenta"),
    (CategoriaIncidente.ACCESO, r"acceso|ingres(o|aron)|inicio de sesion|sesion abierta|usuario (extran|descon)|desconocid|contrasena cambiad|cuenta bloqueada|alguien uso"),
    (CategoriaIncidente.FISICO, r"robo|robaron|perdi|extravi|hurto|laptop|celular|puerta"),
]

AGRAVANTES = r"di (click|clic)|hice (click|clic)|abri el (adjunto|archivo|enlace)|ingrese mi (clave|contrasena|usuario)|puse mi (clave|contrasena)|descargue"

RECOMENDACION = {
    CategoriaIncidente.MALWARE: "Desconectar el equipo de la red (cable y Wi-Fi) sin apagarlo y revisar con TI; verificar copias de seguridad.",
    CategoriaIncidente.FUGA: "Identificar qué datos de pacientes se expusieron y a quién; evaluar la notificación a la ANPD (Ley 29733).",
    CategoriaIncidente.PHISHING: "No responder ni abrir enlaces; bloquear el remitente y, si se ingresó la clave, cambiarla y revisar accesos.",
    CategoriaIncidente.ACCESO: "Revisar los registros de acceso del usuario, cerrar sesiones activas y cambiar la contraseña.",
    CategoriaIncidente.FISICO: "Bloquear las cuentas y sesiones del equipo, y verificar si el disco estaba cifrado.",
    CategoriaIncidente.OTRO: "TI debe revisar el reporte y clasificarlo manualmente.",
}


def _norm(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def evaluar(descripcion, lugar=""):
    texto = _norm(f"{descripcion} {lugar}")
    categoria, activadas = CategoriaIncidente.OTRO, []
    for cat, patron in REGLAS:
        encontradas = sorted({m.group(0) for m in re.finditer(patron, texto)})
        if encontradas:
            categoria, activadas = cat, encontradas
            break
    agravado = bool(re.search(AGRAVANTES, texto))
    if categoria == CategoriaIncidente.MALWARE and re.search(r"ransom|rescate|cifrad|encriptad", texto):
        severidad = "critical"
    elif categoria == CategoriaIncidente.FUGA:
        severidad = "critical" if re.search(r"historia|paciente", texto) else "high"
    elif categoria in (CategoriaIncidente.MALWARE, CategoriaIncidente.ACCESO):
        severidad = "high"
    elif categoria == CategoriaIncidente.PHISHING:
        severidad = "high" if agravado else "medium"
    elif categoria == CategoriaIncidente.FISICO:
        severidad = "high" if re.search(r"laptop|historia|paciente", texto) else "medium"
    else:
        severidad = "low"
    etiqueta = dict(CategoriaIncidente.choices)[categoria]
    motivo = f"palabras clave: {', '.join(activadas[:4])}" if activadas else "sin palabras clave reconocidas"
    resumen = f"Clasificado como «{etiqueta}» con severidad {severidad} ({motivo}"
    resumen += "; la persona indicó que interactuó con el contenido)." if agravado else ")."
    return {
        "categoria": categoria,
        "severidad": severidad,
        "resumen": resumen,
        "recomendacion": RECOMENDACION[categoria],
    }
