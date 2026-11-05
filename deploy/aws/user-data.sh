#!/usr/bin/env bash
# "User data" de la instancia EC2 (Amazon Linux 2023, arm64/Graviton).
# Se pega en: EC2 > Lanzar instancia > Detalles avanzados > Datos de usuario.
# Instala Docker + Compose y deja todo listo; el código se copia después
# (paso "Desplegar la aplicación" de deploy/README_AWS / Pasos_AWS.txt).
set -euxo pipefail

dnf update -y
dnf install -y docker git postgresql16
systemctl enable --now docker
usermod -aG docker ec2-user

ARCH=$(uname -m)            # aarch64 en Graviton, x86_64 en Intel/AMD
case "$ARCH" in
  aarch64) BX=arm64 ;;
  x86_64)  BX=amd64 ;;
esac
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${ARCH}" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
curl -fsSL "https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-${BX}" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-buildx

# 2 GB de swap: la instancia t4g.small tiene 2 GB de RAM y la construcción
# de las imágenes (npm + scikit-learn) puede necesitar un poco más.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -d -m 700 /opt/centinela
# Actualizaciones de seguridad automáticas del sistema operativo.
dnf install -y dnf-automatic
sed -i 's/^apply_updates = .*/apply_updates = yes/' /etc/dnf/automatic.conf
sed -i 's/^upgrade_type = .*/upgrade_type = security/' /etc/dnf/automatic.conf
systemctl enable --now dnf-automatic.timer
