#!/usr/bin/env bash
# Install the demo app onto the current host and start it under systemd.
#
# Contract with the infrastructure repo (ops-agent-iac):
#   - Terraform user_data writes the secret env file /opt/aservice/env
#     (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) BEFORE calling this script.
#   - This script never creates or reads that env file, so it holds no secrets
#     and is safe to keep in a public repo.
#
# Run as root (user_data runs as root):  bash install.sh
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

SRC="$(cd "$(dirname "$0")" && pwd)"

apt-get update -y
apt-get install -y python3 python3-psycopg2

mkdir -p /opt/aservice /var/log/aservice
install -m 0644 "$SRC/app.py" /opt/aservice/app.py
install -m 0644 "$SRC/aservice.service" /etc/systemd/system/aservice.service

systemctl daemon-reload
systemctl enable --now aservice
