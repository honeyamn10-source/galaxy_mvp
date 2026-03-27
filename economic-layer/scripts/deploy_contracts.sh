#!/usr/bin/env bash
set -euo pipefail

# Environment configuration
CHAIN_ID="${CHAIN_ID:-galaxy-1}"
NODE="${CHAIN_NODE:-http://localhost:1317}"
TX_NODE="${CHAIN_TX_NODE:-http://localhost:26657}"
KEYRING_BACKEND="${KEYRING_BACKEND:-test}"
DEPLOYER="${DEPLOYER:-validator}"
GAS="${GAS:-auto}"
GAS_ADJUSTMENT="${GAS_ADJUSTMENT:-1.4}"
FEES="${FEES:-2000ugalaxy}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-./artifacts}"

REGISTRY_WASM="${REGISTRY_WASM:-$ARTIFACTS_DIR/planet_registry.wasm}"
REWARD_WASM="${REWARD_WASM:-$ARTIFACTS_DIR/event_reward.wasm}"
STAKING_WASM="${STAKING_WASM:-$ARTIFACTS_DIR/staking.wasm}"

for file in "$REGISTRY_WASM" "$REWARD_WASM" "$STAKING_WASM"; do
  if [[ ! -f "$file" ]]; then
    echo "missing wasm artifact: $file"
    exit 1
  fi
done

store_contract() {
  local wasm="$1"
  echo "Storing contract: $wasm"
  wasmd tx wasm store "$wasm" \
    --from "$DEPLOYER" \
    --chain-id "$CHAIN_ID" \
    --node "$TX_NODE" \
    --keyring-backend "$KEYRING_BACKEND" \
    --gas "$GAS" \
    --gas-adjustment "$GAS_ADJUSTMENT" \
    --fees "$FEES" \
    -y -o json
}

instantiate_contract() {
  local code_id="$1"
  local label="$2"
  local msg="$3"

  echo "Instantiating code_id=$code_id label=$label"
  wasmd tx wasm instantiate "$code_id" "$msg" \
    --from "$DEPLOYER" \
    --admin "$DEPLOYER" \
    --label "$label" \
    --chain-id "$CHAIN_ID" \
    --node "$TX_NODE" \
    --keyring-backend "$KEYRING_BACKEND" \
    --gas "$GAS" \
    --gas-adjustment "$GAS_ADJUSTMENT" \
    --fees "$FEES" \
    --no-admin=false \
    -y -o json
}

store_contract "$REGISTRY_WASM"
store_contract "$REWARD_WASM"
store_contract "$STAKING_WASM"

echo "Use wasm list-code to retrieve new code IDs, then instantiate:"
echo "  planet-registry: $(printf '{"owner":"%s"}' "$DEPLOYER")"
echo "  event-reward:    $(printf '{"owner":"%s","reward_amount":100,"reward_denom":"ugalaxy"}' "$DEPLOYER")"
echo "  staking:         $(printf '{"owner":"%s","denom":"ugalaxy"}' "$DEPLOYER")"

echo "Example instantiate command:"
echo "  instantiate_contract <code_id> planet-registry '{\"owner\":\"$DEPLOYER\"}'"

echo "Deployment script completed."
