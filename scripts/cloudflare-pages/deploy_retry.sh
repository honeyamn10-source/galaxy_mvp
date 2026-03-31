#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${CF_PAGES_PROJECT_NAME:-${GITHUB_REPOSITORY##*/}}"
BRANCH_NAME="${CF_BRANCH:-main}"
APP_DIR="${APP_DIR:-docs/landing}"
BUILD_COMMAND="${BUILD_COMMAND:-}"
OUTPUT_DIR="${OUTPUT_DIR:-/}"
INSTALL_COMMAND="${INSTALL_COMMAND:-}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  echo "APP_DIR does not exist: ${APP_DIR}"
  exit 1
fi

if [[ -n "${INSTALL_COMMAND}" ]]; then
  echo "Running dependency installation: ${INSTALL_COMMAND}"
  if ! bash -lc "${INSTALL_COMMAND}"; then
    echo "npm ci failed, retrying with npm install"
    npm install
  fi
fi

if [[ -n "${BUILD_COMMAND}" ]]; then
  echo "Running build command: ${BUILD_COMMAND}"
  bash -lc "${BUILD_COMMAND}"
fi

if [[ "${OUTPUT_DIR}" == "/" ]]; then
  DEPLOY_DIR="${APP_DIR}"
else
  DEPLOY_DIR="${OUTPUT_DIR}"
fi

if [[ ! -d "${DEPLOY_DIR}" ]]; then
  echo "Deploy directory missing: ${DEPLOY_DIR}; attempting static fallback"
  if [[ -d "docs/landing" ]]; then
    DEPLOY_DIR="docs/landing"
  else
    exit 1
  fi
fi

echo "Ensuring Pages project exists: ${PROJECT_NAME}"
wrangler pages project create "${PROJECT_NAME}" --production-branch main >/dev/null 2>&1 || true

attempt=1
while [[ "$attempt" -le "$MAX_ATTEMPTS" ]]; do
  echo "Deploy attempt ${attempt}/${MAX_ATTEMPTS}"
  set +e
  DEPLOY_OUTPUT=$(wrangler pages deploy "${DEPLOY_DIR}" --project-name "${PROJECT_NAME}" --branch "${BRANCH_NAME}" 2>&1)
  DEPLOY_EXIT=$?
  set -e

  echo "${DEPLOY_OUTPUT}"

  if [[ "$DEPLOY_EXIT" -eq 0 ]]; then
    URL=$(echo "${DEPLOY_OUTPUT}" | grep -Eo 'https://[^ ]+\.pages\.dev' | tail -n1 || true)
    if [[ -n "${URL}" ]]; then
      echo "pages_url=${URL}" >> "$GITHUB_OUTPUT" 2>/dev/null || true
      echo "Deployment URL: ${URL}"
    fi
    exit 0
  fi

  attempt=$((attempt + 1))
  sleep 5

done

echo "Cloudflare Pages deployment failed after ${MAX_ATTEMPTS} attempts"
exit 1
