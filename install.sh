#!/usr/bin/env bash
# Install the demo app onto the current host and start it under systemd.
#
# Contract with the infrastructure repo (ops-agent-iac):
#   - Terraform user_data writes the secret env file /opt/aservice/env
#     (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) BEFORE calling this script.
#   - This script never creates or reads that env file, so it holds no secrets
#     and is safe to keep in a public repo.
#
# Run as root (user_data runs as root):  sudo bash install.sh
# -x keeps each step visible in cloud-init logs (no secrets are handled here).
set -euxo pipefail

APP_DIR=/opt/aservice
LOG_DIR=/var/log/aservice
ENV_FILE="$APP_DIR/env"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "install.sh must run as root (writes /opt and /etc/systemd)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends python3 python3-psycopg2

install -d -m 0755 "$APP_DIR" "$LOG_DIR"
install -m 0644 "$SRC/app.py" "$APP_DIR/app.py"
install -m 0644 "$SRC/aservice.service" /etc/systemd/system/aservice.service

# The secret env file is the infrastructure's responsibility. Warn (don't fail)
# so a missing file is diagnosable instead of surfacing as a silent crash-loop.
if [[ ! -f "$ENV_FILE" ]]; then
  echo "WARNING: $ENV_FILE not found — the app will crash until Terraform writes it." >&2
fi

systemctl daemon-reload
systemctl enable --now aservice
