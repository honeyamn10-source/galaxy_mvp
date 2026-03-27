#!/usr/bin/env bash
set -euo pipefail

# Scaffolds a CosmWasm contract from official template.
# Requires: cargo-generate
# Usage: CONTRACT_NAME=planet-registry ./scaffold_contracts.sh

CONTRACT_NAME="${CONTRACT_NAME:-planet-registry}"
TEMPLATE_REPO="${COSMWASM_TEMPLATE_REPO:-https://github.com/CosmWasm/cw-template.git}"
TARGET_DIR="${TARGET_DIR:-./contracts}"

if ! command -v cargo-generate >/dev/null 2>&1; then
  echo "cargo-generate is required. Install with: cargo install cargo-generate"
  exit 1
fi

cargo generate \
  --git "$TEMPLATE_REPO" \
  --name "$CONTRACT_NAME" \
  --define contract_name="$CONTRACT_NAME" \
  --destination "$TARGET_DIR"

echo "Contract scaffolded at $TARGET_DIR/$CONTRACT_NAME"
