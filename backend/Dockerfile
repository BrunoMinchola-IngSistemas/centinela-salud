# Imagen de la API (Django + gunicorn) y del programador de tareas.
# Multi-arquitectura: funciona en EC2 Graviton (arm64) y en x86_64.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# iputils-ping: barrido de red (HU01) cuando se habilita; curl: chequeos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Certificados de Amazon RDS para conectarse con sslmode=verify-full
# (cifrado en tránsito verificado hacia la base de datos).
RUN mkdir -p /etc/ssl/rds \
    && curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /etc/ssl/rds/global-bundle.pem

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Archivos estáticos (admin de Django y API navegable) servidos por WhiteNoise.
RUN DJANGO_SECRET_KEY=solo-para-construir-la-imagen python manage.py collectstatic --noinput

# Nunca correr como root dentro del contenedor.
RUN useradd --create-home --uid 10001 centinela && mkdir -p /app/media && chown -R centinela /app/media
USER centinela

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/salud/ || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "180", "--access-logfile", "-"]
