# Phase V Economic Layer

This folder contains the Phase V token economy contracts and deployment scripts.

## Contracts

- planet-registry: maps device IDs to wallet addresses.
- event-reward: rewards verified events in GALAXY tokens.
- staking: stake/unstake and validator slashing primitives.

## Build

cd contracts
cargo build --release --target wasm32-unknown-unknown

## Test

bash ../scripts/run_contract_tests.sh

## Deploy

bash ../scripts/deploy_contracts.sh

Deployment expects wasm artifacts in ./artifacts and a local wasmd-compatible endpoint.

## Scaffold from cosmwasm-template

bash scripts/scaffold_contracts.sh

Set CONTRACT_NAME to customize the generated contract directory.
