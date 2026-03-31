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

detect_os() {
  case "$(uname -s)" in
    Linux) echo "linux" ;;
    Darwin) echo "macos" ;;
    *) echo "unsupported" ;;
  esac
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

  case "$(detect_os)" in
    linux) install_docker_linux ;;
    macos) install_docker_macos ;;
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

port_in_use() {
  local port="$1"
  if command_exists ss; then
    ss -ltn | awk '{print $4}' | grep -q ":${port}$"
    return
  fi
  if command_exists lsof; then
    lsof -iTCP -sTCP:LISTEN -Pn | grep -q ":${port} "
    return
  fi
  return 1
}

check_ports() {
  local ports=(1317 7001 7002 8081 8082 8100 8200 8300 8400 8500 8600)
  local busy=()
  for p in "${ports[@]}"; do
    if port_in_use "$p"; then
      busy+=("$p")
    fi
  done

  if [[ ${#busy[@]} -gt 0 ]]; then
    echo "These required ports are in use: ${busy[*]}"
    echo "Free them and re-run installer."
    exit 1
  fi
}

open_dashboard() {
  local url="$1"
  case "$(detect_os)" in
    linux)
      if command_exists xdg-open; then
        xdg-open "$url" >/dev/null 2>&1 || true
      fi
      ;;
    macos)
      open "$url" >/dev/null 2>&1 || true
      ;;
  esac
}

ask_with_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "${prompt} [${default}]: " value
  if [[ -z "$value" ]]; then
    echo "$default"
  else
    echo "$value"
  fi
}

write_env() {
  local edge_api_key="$1"
  local rtsp_url="$2"
  local region="$3"

  cat > "${WORKDIR}/.env" <<EOF
# Galaxy MVP runtime configuration
EDGE_TENANT_API_KEY=${edge_api_key}
EDGE_DEVICE_ID=planet-01
RTSP_URL=${rtsp_url}
COMPLIANCE_DEFAULT_REGION=${region}
MODEL_PATH=/models/default-model.json
OPENWEATHER_API_KEY=
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=deepseek-llm:6.7b
EOF
}

draw_progress() {
  local current="$1"
  local total="$2"
  local width=28
  local fill=$((current * width / total))
  local empty=$((width - fill))
  local pct=$((current * 100 / total))
  local bar
  bar="$(printf '%*s' "$fill" '' | tr ' ' '#')$(printf '%*s' "$empty" '' | tr ' ' '-')"
  printf "\rPulling images [%s] %3d%% (%d/%d)" "$bar" "$pct" "$current" "$total"
}

pull_images() {
  local total="${#IMAGES[@]}"
  local i=0
  for image in "${IMAGES[@]}"; do
    i=$((i + 1))
    draw_progress "$i" "$total"
    docker pull "$image" >/dev/null || echo "\nWarning: failed to pull ${image}"
  done
  echo
}

main() {
  print_step "Galaxy MVP installer"
  ensure_docker
  ensure_compose

  print_step "Checking local ports"
  check_ports

  print_step "Collecting runtime configuration"
  local edge_api_key
  local rtsp_url
  local region
  edge_api_key="$(ask_with_default 'Edge API key' 'edge-planet-local')"
  rtsp_url="$(ask_with_default 'RTSP URL (leave blank to simulate events)' '')"
  region="$(ask_with_default 'Compliance region (eu/us/apac)' 'eu')"

  print_step "Preparing workspace"
  mkdir -p "${WORKDIR}"
  cd "${WORKDIR}"

  print_step "Downloading compose file"
  curl -fsSL "${COMPOSE_URL}" -o docker-compose.yml
  write_env "$edge_api_key" "$rtsp_url" "$region"

  print_step "Pulling prebuilt images from GHCR"
  pull_images

  print_step "Starting Galaxy stack"
  docker compose up -d

  echo
  echo "Galaxy MVP is running."
  echo "Dashboard: ${DASHBOARD_URL}"
  open_dashboard "${DASHBOARD_URL}"
}

main "$@"
