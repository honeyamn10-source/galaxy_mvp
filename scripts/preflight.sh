#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running or not reachable. Start Docker and try again."
  exit 1
fi

services=$(docker compose ps --format json 2>/dev/null || true)
if [[ -z "$services" ]]; then
  echo "No Compose services are running yet."
  exit 0
fi

python3 - "$services" <<'PY'
import json
import os
import subprocess
import sys

raw = sys.argv[1]
try:
    items = json.loads(raw)
except Exception:
    print("Unable to parse docker compose status")
    sys.exit(1)

needs_restart = []
for item in items:
    service = item.get("Service") or item.get("service")
    state = (item.get("State") or item.get("state") or "").lower()
    health = (item.get("Health") or item.get("health") or "").lower()
    if service and (state not in {"running", "healthy"} or health not in {"", "healthy"}):
        needs_restart.append(service)

for service in needs_restart:
    print(f"Restarting {service}...")
    subprocess.run(["docker", "compose", "restart", service], check=False)

if needs_restart:
    print("Restarted unhealthy services:", ", ".join(needs_restart))
else:
    print("All visible compose services are healthy or running.")
PY
