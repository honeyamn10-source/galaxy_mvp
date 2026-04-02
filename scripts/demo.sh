#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

bash ./scripts/preflight.sh
make swarm-up

echo "Waiting for services to settle..."
sleep 10

bash ./scripts/auto-events.sh >/tmp/galaxy-auto-events.log 2>&1 &
auto_pid=$!
trap 'kill "$auto_pid" >/dev/null 2>&1 || true' EXIT

echo "Dashboard: http://localhost:8000"
echo "Landing: http://localhost:8080"

echo "Opening dashboard..."
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:8000 >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open http://localhost:8000 >/dev/null 2>&1 || true
fi

echo "Auto events are running in the background."
wait "$auto_pid"
