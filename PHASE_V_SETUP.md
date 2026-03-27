# Phase V Setup - Expansion and Economic Layer

## Objective

Phase V introduces business capabilities on top of the autonomous galaxy runtime:

- token economy and staking,
- CosmWasm contract scaffolding and deployment scripts,
- enterprise webhook delivery,
- compliance policies (GDPR/HIPAA/NIST-style audit logs),
- optional Hermes IBC relayer profile.

## Components Added

- economic-layer/contracts
  - planet-registry
  - event-reward
  - staking
- expansion-layer/webhook-service
- expansion-layer/compliance-engine
- expansion-layer/hermes

## Start Phase V Stack

1. Generate certs:

make swarm-certs

2. Start full stack:

make swarm-up

3. Run integration test:

make test

## Key Endpoints

- Authority health: http://localhost:1317/health
- Authority events: http://localhost:1317/galaxy/v1/events
- Economy register: POST http://localhost:1317/economy/v1/planet/register
- Economy device balance: GET http://localhost:1317/economy/v1/balance/by-device/{device_id}
- Economy stake: POST http://localhost:1317/economy/v1/stake
- Economy slash: POST http://localhost:1317/economy/v1/slash
- CosmWasm contracts list: GET http://localhost:1317/cosmwasm/wasm/v1/contracts
- Webhook service health: http://localhost:8500/health
- Webhook subscriptions: POST http://localhost:8500/webhooks/register
- Compliance health: http://localhost:8400/health
- Compliance transform: POST http://localhost:8400/transform

## Environment Variables

### Authority (galaxyd)

- CHAIN_REWARD_UGALAXY
- CHAIN_SUBMISSION_FEE_UGALAXY
- CHAIN_ALLOW_FEE_OVERDRAFT
- CHAIN_COSMWASM_ENABLED
- CHAIN_COMPLIANCE_URL
- CHAIN_COMPLIANCE_TIMEOUT

### Webhook Service

- WEBHOOK_DATABASE_URL
- WEBHOOK_AUTHORITY_EVENTS_URL
- WEBHOOK_POLL_INTERVAL_SECONDS
- WEBHOOK_MAX_RETRIES
- WEBHOOK_BACKOFF_BASE_SECONDS

### Compliance Engine

- COMPLIANCE_DEFAULT_REGION
- COMPLIANCE_HIPAA_EVENT_TYPES
- COMPLIANCE_PII_KEYS
- COMPLIANCE_ENCRYPTION_KEY
- COMPLIANCE_AUDIT_LOG_PATH
- COMPLIANCE_DATABASE_URL

## CosmWasm Contracts

Contract source lives in economic-layer/contracts.

Run tests:

make contracts-test

Deploy script:

bash economic-layer/scripts/deploy_contracts.sh

## Hermes IBC Relayer (Optional)

- Config: expansion-layer/hermes/config.toml
- Start profile:

make ibc-up

- See setup commands in:
  - expansion-layer/hermes/README.md

## Integration Test Coverage

test-phase1.py now validates:

- event flow edge -> swarm -> authority,
- FL and predictive service smoke checks,
- token reward balance increase for registered planet,
- webhook delivery into debug receiver,
- compliance masking/encryption behavior.

## Host Dependency Notes

If local checks fail due to missing tools:

- Install Go to compile authority-chain and swarm-node.
- Install Rust/Cargo to run CosmWasm contract tests.
- Install Docker and Docker Compose for full stack validation.
