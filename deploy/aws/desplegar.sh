#!/usr/bin/env bash
# Despliegue / actualización en la EC2 (correr con sudo, por Session Manager).
#   sudo bash /opt/centinela/app/deploy/aws/desplegar.sh
# 1) baja las variables de Parameter Store, 2) construye las imágenes,
# 3) migra la base (y aplica RLS), 4) levanta api + programador + web.
set -euo pipefail
cd "$(dirname "$0")/.."           # carpeta deploy/
ENV=/opt/centinela/.env

bash aws/cargar_secretos.sh /centinela/prod "$ENV"
COMPOSE="docker compose --env-file $ENV -f docker-compose.yml -f docker-compose.cloudwatch.yml"

$COMPOSE build
$COMPOSE run --rm --no-deps api python manage.py migrate --noinput
$COMPOSE run --rm --no-deps api python manage.py check --deploy --fail-level ERROR
$COMPOSE up -d --remove-orphans
docker image prune -f

echo "Listo. Estado:"
$COMPOSE ps
