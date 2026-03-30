#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   GHCR_OWNER=honeyamn10-source GHCR_TAG=latest ./scripts/push-images-ghcr.sh

GHCR_OWNER="${GHCR_OWNER:-honeyamn10-source}"
GHCR_TAG="${GHCR_TAG:-latest}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not available"
  exit 1
fi

if [[ -z "${CR_PAT:-}" ]]; then
  echo "Set CR_PAT to a GitHub token with package write scope, then re-run."
  echo "Example: export CR_PAT=ghp_xxx"
  exit 1
fi

echo "${CR_PAT}" | docker login ghcr.io -u "${GHCR_OWNER}" --password-stdin

build_and_push() {
  local context="$1"
  local image_name="$2"
  local image="ghcr.io/${GHCR_OWNER}/${image_name}:${GHCR_TAG}"

  echo "Building ${image} from ${context}"
  docker build -t "${image}" "${context}"
  docker push "${image}"
}

build_and_push "authority-chain" "galaxy-authority-chain"
build_and_push "swarm-node" "galaxy-swarm-node"
build_and_push "edge-planet" "galaxy-edge-planet"
build_and_push "intelligence-layer/fl-aggregator" "galaxy-fl-aggregator"
build_and_push "intelligence-layer/predictive-service" "galaxy-predictive-service"
build_and_push "expansion-layer/compliance-engine" "galaxy-compliance-engine"
build_and_push "expansion-layer/webhook-service" "galaxy-webhook-service"
build_and_push "llm-service" "galaxy-llm-service"

echo "All images pushed to ghcr.io/${GHCR_OWNER} with tag ${GHCR_TAG}"
