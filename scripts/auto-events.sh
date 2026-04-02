#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

while true; do
  confidence=$(python3 - <<'PY'
from random import randint
print(f"0.{randint(1,9)}")
PY
)
  curl -s -X POST http://localhost:8100/events \
    -H "Content-Type: application/json" \
    -d "{\"device_id\":\"auto\",\"event_type\":\"motion\",\"confidence\":$confidence}" >/dev/null || true
  sleep 2
done
