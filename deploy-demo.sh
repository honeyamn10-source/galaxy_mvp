#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on a fresh Ubuntu 22.04 VM: sudo bash deploy-demo.sh"
  exit 1
fi

STACK_DIR="/opt/galaxy-mvp"
REPO_URL="https://github.com/honeyamn10-source/galaxy_mvp.git"
DASHBOARD_UPSTREAM="http://127.0.0.1:8000"
AUTH_USER="${DEMO_AUTH_USER:-galaxy}"
AUTH_PASS="${DEMO_AUTH_PASS:-galaxy-demo-2026}"

echo "==> Updating system packages"
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git apache2-utils nginx

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

echo "==> Ensuring Docker Compose plugin"
if ! docker compose version >/dev/null 2>&1; then
  apt-get install -y docker-compose-plugin
fi

echo "==> Enabling Docker service"
systemctl enable docker
systemctl restart docker

if [[ ! -d "${STACK_DIR}" ]]; then
  echo "==> Cloning Galaxy MVP"
  git clone "${REPO_URL}" "${STACK_DIR}"
else
  echo "==> Updating existing Galaxy MVP checkout"
  git -C "${STACK_DIR}" pull --ff-only
fi

cat > "${STACK_DIR}/.env" <<'EOF'
EDGE_TENANT_API_KEY=edge-planet-local
EDGE_DEVICE_ID=planet-01
RTSP_URL=
COMPLIANCE_DEFAULT_REGION=eu
MODEL_PATH=/models/default-model.json
OPENWEATHER_API_KEY=
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=deepseek-llm:6.7b
EOF

mkdir -p "${STACK_DIR}/models"

echo "==> Starting Galaxy stack"
docker compose -f "${STACK_DIR}/docker-compose.yml" --env-file "${STACK_DIR}/.env" up -d --build

echo "==> Configuring nginx basic auth"
htpasswd -bc /etc/nginx/.htpasswd "${AUTH_USER}" "${AUTH_PASS}"

cat > /etc/nginx/sites-available/galaxy-demo <<EOF
server {
  listen 80;
  server_name _;

  location / {
    auth_basic "Galaxy Demo";
    auth_basic_user_file /etc/nginx/.htpasswd;

    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_pass ${DASHBOARD_UPSTREAM};
  }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/galaxy-demo /etc/nginx/sites-enabled/galaxy-demo
nginx -t
systemctl restart nginx

PUBLIC_IP="$(hostname -I | awk '{print $1}')"

echo
echo "Galaxy demo is live."
echo "URL: http://${PUBLIC_IP}"
echo "Basic auth user: ${AUTH_USER}"
echo "Basic auth password: ${AUTH_PASS}"
echo "Stack path: ${STACK_DIR}"
