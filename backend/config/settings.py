"""
Configuración de Django para Centinela Salud.

Todo lo que cambia entre la PC de desarrollo y AWS se lee de variables
de entorno (archivo backend/.env en la PC; en AWS, Parameter Store ->
/opt/centinela/.env, ver deploy/). Valores por defecto SEGUROS:
DEBUG apagado, sin clave secreta por defecto en producción, HTTPS
obligatorio cuando DJANGO_HTTPS=True.
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(nombre, defecto=False):
    return os.getenv(nombre, str(defecto)).strip().lower() in ("1", "true", "si", "sí", "yes")


def _lista(nombre, defecto=""):
    return [x.strip() for x in os.getenv(nombre, defecto).split(",") if x.strip()]


TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

# --- Núcleo -------------------------------------------------------------------

DEBUG = _bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "solo-desarrollo-no-usar-en-produccion-" + "x" * 20
    else:
        raise ImproperlyConfigured("Falta DJANGO_SECRET_KEY (obligatoria con DJANGO_DEBUG=False).")

ALLOWED_HOSTS = _lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Clave aparte para seudonimizar datos personales (common/privacidad.py).
PSEUDONIMIZACION_CLAVE = os.getenv("PSEUDONIMIZACION_CLAVE", "")

# Admin de Django: útil en la PC; en la nube se apaga por defecto porque
# su login no pasa por el bloqueo de intentos ni el segundo factor.
ADMIN_DJANGO_HABILITADO = _bool("DJANGO_ADMIN_HABILITADO", DEBUG)
ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin/")

# --- Aplicaciones ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    # Apps del dominio (Centinela Salud)
    "accounts",
    "assets",
    "controls",
    "vulnerabilities",
    "remediation",
    "evidence",
    "integrations",
    "governance",
    "incidents",
    "notificaciones",
    "informes",
    "common",
]

MIDDLEWARE = [
    "common.middleware.ResetRLSMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# En AWS la consola y la API se sirven desde el MISMO dominio (Caddy),
# así que CORS solo hace falta en desarrollo (Vite en :5173).
CORS_ALLOWED_ORIGINS = _lista("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_EXPOSE_HEADERS = ["Content-Disposition", "X-Integridad-SHA256"]
CSRF_TRUSTED_ORIGINS = _lista("CSRF_TRUSTED_ORIGINS", "")

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.authentication.RLSTokenAuthentication",
        "common.authentication.RLSSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["common.permissions.IsAuthenticatedRoleAware"],
    # Límite de peticiones: freno a fuerza bruta y abuso. "login" es por IP.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100000/min" if TESTING else os.getenv("THROTTLE_ANON", "60/min"),
        "user": "100000/min" if TESTING else os.getenv("THROTTLE_USER", "600/min"),
        "login": "100000/min" if TESTING else os.getenv("THROTTLE_LOGIN", "10/min"),
    },
}

# Horas de vida del token de sesión (HU29 / RNF-04).
TOKEN_TTL_HORAS = int(os.getenv("TOKEN_TTL_HORAS", "12"))

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de datos -----------------------------------------------------------
# SQLite si POSTGRES_DB está vacío (PC); PostgreSQL (RDS en AWS) si tiene valor.
# En RDS: POSTGRES_SSLMODE=verify-full y POSTGRES_SSLROOTCERT con el bundle de
# certificados de AWS (cifrado en tránsito verificado, Ley 29733).

if os.getenv("POSTGRES_DB"):
    _opciones_pg = {"sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")}
    if os.getenv("POSTGRES_SSLROOTCERT"):
        _opciones_pg["sslrootcert"] = os.getenv("POSTGRES_SSLROOTCERT")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "centinela"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": _opciones_pg,
            # Sin conexiones persistentes: cada petición fija y limpia su
            # rol RLS (common/middleware.py); así es imposible "heredarlo".
            "CONN_MAX_AGE": 0,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

# --- Contraseñas ---------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if TESTING:
    # Solo en `manage.py test`: hash rápido para que crear usuarios en
    # cada prueba no tarde medio segundo. Nunca aplica al servidor real.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Idioma y zona horaria -----------------------------------------------------

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

# --- Archivos estáticos y subidos ----------------------------------------------
# Estáticos (admin de Django): WhiteNoise. Archivos subidos (evidencias,
# reportes): S3 privado y cifrado si AWS_STORAGE_BUCKET_NAME tiene valor;
# en la PC, carpeta backend/media (que NO se publica por URL: todo se
# descarga a través de la API, con sesión y registro de auditoría).

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
if AWS_STORAGE_BUCKET_NAME:
    _almacen = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": os.getenv("AWS_REGION", "us-east-1"),
            "default_acl": None,  # el bucket bloquea todo acceso público
            "querystring_auth": True,
            "file_overwrite": False,
            "object_parameters": {"ServerSideEncryption": os.getenv("AWS_S3_SSE", "aws:kms")},
            # Credenciales: rol IAM de la instancia EC2 (nunca claves en el .env).
        },
    }
else:
    _almacen = {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": MEDIA_ROOT}}

STORAGES = {
    "default": _almacen,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# --- Correo --------------------------------------------------------------------
# En AWS: Amazon SES por SMTP (EMAIL_HOST=email-smtp.<region>.amazonaws.com).
# Sin EMAIL_HOST, los avisos se ven igual en la campana de la consola.

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Centinela Salud <no-responder@localhost>")
if os.getenv("EMAIL_HOST"):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.getenv("EMAIL_HOST"),
                "port": int(os.getenv("EMAIL_PORT", "587")),
                "username": os.getenv("EMAIL_HOST_USER", ""),
                "password": os.getenv("EMAIL_HOST_PASSWORD", ""),
                "use_tls": True,
                "timeout": 10,
            },
        },
    }
    SILENCED_SYSTEM_CHECKS = []
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
    # Correo opcional: sin SMTP configurado el aviso queda en la consola.
    SILENCED_SYSTEM_CHECKS = ["mail.E001"]

# --- Seguridad HTTP (paso A del despliegue) ----------------------------------------
# DJANGO_HTTPS=True en AWS (Caddy termina TLS y reenvía X-Forwarded-Proto).

HTTPS = _bool("DJANGO_HTTPS", False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = HTTPS
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if HTTPS else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Caddy hace la redirección a HTTPS y el chequeo de salud entra por HTTP interno.
SECURE_REDIRECT_EXEMPT = [r"^api/salud/$"]

# --- Comportamiento del agente -------------------------------------------------

# Barrido de red local (HU01): en la nube no tiene sentido (no ve la red de la clínica).
DESCUBRIMIENTO_RED_HABILITADO = _bool("DESCUBRIMIENTO_RED_HABILITADO", True)
# Datos de demostración en los conectores no configurados (ver integrations/demo.py).
INTEGRACIONES_DEMO = _bool("INTEGRACIONES_DEMO", DEBUG)

# --- Registro (logs a la salida estándar -> Docker -> CloudWatch Logs) ----------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
if TESTING:
    LOGGING["root"]["level"] = "CRITICAL"
