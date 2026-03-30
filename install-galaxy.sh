#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="honeyamn10-source"
REPO_NAME="galaxy_mvp"
REPO_REF="main"
COMPOSE_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_REF}/docker-compose.yml"
WORKDIR="${HOME}/galaxy-mvp"
DASHBOARD_URL="http://localhost:8000"

IMAGES=(
  "ghcr.io/${REPO_OWNER}/galaxy-authority-chain:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-swarm-node:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-edge-planet:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-fl-aggregator:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-predictive-service:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-compliance-engine:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-webhook-service:latest"
  "ghcr.io/${REPO_OWNER}/galaxy-llm-service:latest"
)

print_step() {
  printf "\n==> %s\n" "$1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

install_docker_linux() {
  print_step "Installing Docker (Linux)"
  curl -fsSL https://get.docker.com | sh
  if command_exists sudo; then
    sudo usermod -aG docker "$USER" || true
  fi
}

install_docker_macos() {
  print_step "Installing Docker Desktop (macOS)"
  if command_exists brew; then
    brew install --cask docker
    open -a Docker || true
  else
    echo "Homebrew is required to auto-install Docker Desktop on macOS."
    echo "Install Homebrew: https://brew.sh"
    exit 1
  fi
}

ensure_docker() {
  if command_exists docker; then
    return
  fi

  case "$(uname -s)" in
    Linux)
      install_docker_linux
      ;;
    Darwin)
      install_docker_macos
      ;;
    *)
      echo "Unsupported OS: $(uname -s). Install Docker manually and re-run."
      exit 1
      ;;
  esac

  echo "Docker was installed. Re-run this script after Docker is ready."
  exit 1
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    return
  fi

  echo "Docker Compose plugin is missing."
  echo "Install Docker Compose plugin and re-run."
  exit 1
}

open_dashboard() {
  local url="$1"
  case "$(uname -s)" in
    Linux)
      if command_exists xdg-open; then
        xdg-open "$url" >/dev/null 2>&1 || true
      fi
      ;;
    Darwin)
      open "$url" >/dev/null 2>&1 || true
      ;;
  esac
}

write_env_if_missing() {
  if [[ -f "${WORKDIR}/.env" ]]; then
    return
  fi

  cat > "${WORKDIR}/.env" <<'EOF'
# Galaxy MVP runtime configuration
EDGE_TENANT_API_KEY=edge-planet-local
EDGE_DEVICE_ID=planet-01
OPENWEATHER_API_KEY=
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=deepseek-llm:6.7b
EOF
}

main() {
  print_step "Galaxy MVP installer"
  ensure_docker
  ensure_compose

  print_step "Preparing workspace"
  mkdir -p "${WORKDIR}"
  cd "${WORKDIR}"

  print_step "Downloading compose file"
  curl -fsSL "${COMPOSE_URL}" -o docker-compose.yml
  write_env_if_missing

  print_step "Pulling prebuilt images"
  for image in "${IMAGES[@]}"; do
    echo "Pulling ${image}"
    docker pull "${image}" || echo "Warning: failed to pull ${image}"
  done

  print_step "Starting Galaxy stack"
  docker compose up -d

  echo
  echo "Galaxy MVP is running."
  echo "Dashboard: ${DASHBOARD_URL}"
  open_dashboard "${DASHBOARD_URL}"
}

main "$@"
