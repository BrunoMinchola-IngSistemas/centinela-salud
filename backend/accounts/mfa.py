"""
HU29: segundo factor con TOTP (RFC 6238), compatible con Google
Authenticator, Microsoft Authenticator, Authy, etc.

Implementado con la librería estándar (hmac + base64) para no agregar
dependencias; la prueba unitaria usa los vectores del propio RFC.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

import segno

PERIODO = 30
DIGITOS = 6
VENTANA = 1  # acepta el código anterior y el siguiente (desfase de reloj)
EMISOR = "Centinela Salud"


def nuevo_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _clave(secreto):
    relleno = "=" * (-len(secreto) % 8)
    return base64.b32decode(secreto.upper() + relleno)


def hotp(clave_bytes, contador, digitos=DIGITOS, algoritmo=hashlib.sha1):
    mac = hmac.new(clave_bytes, struct.pack(">Q", contador), algoritmo).digest()
    desplazamiento = mac[-1] & 0x0F
    numero = struct.unpack(">I", mac[desplazamiento : desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(numero % (10**digitos)).zfill(digitos)


def codigo_actual(secreto, instante=None):
    return hotp(_clave(secreto), int((instante or time.time()) // PERIODO))


def verificar(secreto, codigo, instante=None):
    codigo = "".join(ch for ch in str(codigo or "") if ch.isdigit())
    if not secreto or len(codigo) != DIGITOS:
        return False
    paso = int((instante or time.time()) // PERIODO)
    clave = _clave(secreto)
    return any(hmac.compare_digest(hotp(clave, paso + d), codigo) for d in range(-VENTANA, VENTANA + 1))


def uri(secreto, usuario):
    etiqueta = quote(f"{EMISOR}:{usuario}")
    return f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(EMISOR)}&algorithm=SHA1&digits={DIGITOS}&period={PERIODO}"


def qr_svg_data_uri(texto):
    return segno.make(texto, error="m").svg_data_uri(scale=5, border=2)
