#!/usr/bin/env bash
# Baja los parámetros /centinela/prod/* de AWS Systems Manager Parameter
# Store a /opt/centinela/.env (solo lectura para root). Lo corre el
# arranque de la instancia y cada despliegue. Usa el rol IAM de la EC2:
# no hay claves de AWS escritas en ningún archivo.
set -euo pipefail

PREFIJO="${1:-/centinela/prod}"
DESTINO="${2:-/opt/centinela/.env}"

TOKEN=$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
REGION=$(curl -sS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)

TMP=$(mktemp)
chmod 600 "$TMP"
aws ssm get-parameters-by-path \
  --region "$REGION" --path "$PREFIJO" --recursive --with-decryption \
  --query 'Parameters[].[Name,Value]' --output text |
while IFS=$'\t' read -r nombre valor; do
  printf '%s=%s\n' "${nombre##*/}" "$valor"
done > "$TMP"

if ! grep -q '^DJANGO_SECRET_KEY=' "$TMP"; then
  echo "ERROR: no se encontraron parámetros en $PREFIJO (¿región o permisos del rol?)" >&2
  rm -f "$TMP"
  exit 1
fi
grep -q '^AWS_REGION=' "$TMP" || echo "AWS_REGION=$REGION" >> "$TMP"

install -d -m 700 "$(dirname "$DESTINO")"
mv "$TMP" "$DESTINO"
chmod 600 "$DESTINO"
echo "Variables cargadas en $DESTINO ($(wc -l < "$DESTINO") líneas)."
