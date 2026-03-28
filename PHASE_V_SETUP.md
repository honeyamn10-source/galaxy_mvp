# Phase V Setup - Expansion & Economic Layer

## Objective

Phase V adds the final business capabilities to Galaxy:

1. **Token Economy** – reward planets with GALAXY tokens for verified events
2. **IBC Gateway** – bridge to other ecosystems (Osmosis testnet, Ethereum via Gravity Bridge)
3. **Enterprise Integrations** – webhook delivery with retries and compliance controls
4. **Compliance Engine** – GDPR/HIPAA/NIST policy enforcement

## What Is Included

### Economic Layer
- **CosmWasm Contracts** (Rust):
  - `planet-registry`: Maps device IDs to wallet addresses
  - `event-reward`: Distributes GALAXY tokens for verified events (confidence > 0.8)
  - `staking`: Validator stake management and slashing logic

### Expansion Layer
- **Webhook Delivery Service** (Python FastAPI):
  - Subscribes to verified events from authority
  - Delivers to tenant-configured URLs with exponential backoff (4 retries)
  - Dead-letter queue for failed deliveries
  - Audit logging of all delivery attempts

- **Compliance Engine** (Python FastAPI):
  - Middleware that applies regional policies before storage
  - GDPR: Masks PII fields (names, face IDs) in EU regions
  - HIPAA: Encrypts health-related events
  - NIST: Audit logs meet federal standards  
  - Pluggable policy engine (per-tenant configuration)

- **IBC Relayer** (Hermes):
  - Connects `galaxy-1` chain to `osmo-test-5` (Osmosis testnet)
  - Automatic relay of verified events to other ecosystems
  - Two-way communication for cross-chain queries

## Architecture Flow

```
Edge Planet → Swarm Mesh → Authority Chain → 
  ├─→ Compliance Engine (mask PII, encrypt, audit)
  ├─→ Webhook Service (deliver to tenant URLs)
  ├─→ Token Economy (reward validators, pay fees)
  └─→ IBC Relayer (broadcast to other chains)
```

## Start Phase V Stack

### 1. Generate Local TLS Certificates

```bash
make swarm-certs
```

### 2. Build and Start All Services

```bash
make swarm-up
```

This starts:
- PostgreSQL (event store, quotas, tenant data)
- Redis (real-time pub/sub)
- Authority chain with galaxy module (on port 1317)
- 2x Swarm nodes (with mTLS, on ports 7001-7002, 8443-8444)
- Edge planet simulator (on port 8100)
- FL Aggregator (on port 8200)
- Predictive service (on port 8300)
- Webhook service (on port 8500)
- Compliance engine (on port 8400)

### 3. Optional: Start IBC Relayer

```bash
make ibc-up
```

Starts Hermes relayer (requires osmo-test-5 network access; uses Osmosis testnet endpoints).

## Phase V Integration Test

Run the complete end-to-end test:

```bash
make test
# or
python3 test-phase-v.py
```

This validates:
- All services are healthy
- Events flow from edge → authority
- Compliance policies are applied
- Webhooks register and (attempt to) deliver
- Token contract structure is in place
- FL and prediction services are operational

## Configuration

### Environment Variables

All services use environment variable configuration (no hardcoded values):

#### Authority Chain
```env
CHAIN_ID=galaxy-1
CHAIN_REWARD_UGALAXY=100          # Tokens per verified event
CHAIN_SUBMISSION_FEE_UGALAXY=5    # Tenants pay this per event
CHAIN_COSMWASM_ENABLED=true       # Enable smart contracts
CHAIN_COMPLIANCE_URL=http://compliance-engine:8400
```

#### Webhook Service
```env
WEBHOOK_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/galaxy
WEBHOOK_AUTHORITY_EVENTS_URL=http://authority-chain:1317/galaxy/v1/events
WEBHOOK_POLL_INTERVAL_SECONDS=5
WEBHOOK_MAX_RETRIES=4
WEBHOOK_BACKOFF_BASE_SECONDS=0.5  # Exponential backoff
```

#### Compliance Engine
```env
COMPLIANCE_DEFAULT_REGION=eu       # Default for unknown tenants
COMPLIANCE_HIPAA_EVENT_TYPES=health_alert,patient_fall
COMPLIANCE_PII_KEYS=name,face_id,person_name
COMPLIANCE_ENCRYPTION_KEY=...      # Change in production!
COMPLIANCE_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/galaxy
```

#### Hermes Relayer
```env
HERMES_CONFIG=/config/config.toml
RUST_LOG=info
```
See `expansion-layer/hermes/config.toml` for chain definitions.

## Key Endpoints

### Authority Chain / Cosmos REST
- `GET /health` – blockchain health
- `GET /galaxy/v1/events` – query verified events
- `GET /cosmos/base/tendermint/v1beta1/blocks/latest` – latest block
- `POST /cosmos/tx/v1beta1/txs` – submit transactions

### Webhook Service
- `POST /webhooks/register` – register tenant webhook URL
- `GET /webhooks/subscriptions` – list active subscriptions
- `GET /webhooks/dead-letters` – events that failed to deliver
- `GET /debug/received` – mock receiver for testing

### Compliance Engine
- `POST /transform` – apply regional policies to event
- `GET /audit/recent` – view audit log entries

### Token Contracts (Cosmos ecosystem)
- Query planet registry: `wasmd query wasm contract-state smart <contract> '{"planet":{"device_id":".."}}'`
- Query reward status: `wasmd query wasm contract-state smart <contract> '{"reward_status":{"tx_hash":".."}}'`
- Query staked amount: `wasmd query wasm contract-state smart <contract> '{"stake":{"wallet":".."}}'`

## Deploying Token Contracts

### Build WASM Artifacts

```bash
cd economic-layer/contracts
cargo build --release --target wasm32-unknown-unknown
```

Artifacts will be in `target/wasm32-unknown-unknown/release/`.

### Run Unit Tests

```bash
make contracts-test
# or
bash economic-layer/scripts/run_contract_tests.sh
```

### Deploy to Authority Chain

1. Ensure authority chain is running with CosmWasm enabled
2. Store contracts on chain:

```bash
bash economic-layer/scripts/deploy_contracts.sh
```

This stores the three WASM files and prints code IDs.

3. Instantiate each contract with proper initialization messages:

```bash
# Get the code IDs from previous step, then:
wasmd tx wasm instantiate <REGISTRY_CODE_ID> \
  '{"owner":"galaxy1validator"}' \
  --label planet-registry \
  --from validator \
  --chain-id galaxy-1 \
  -y -o json
```

The script provides templates for all three contracts.

### Verification

Query contract state:

```bash
# List all contracts on chain
wasmd query wasm list-code

# Query planet registry
wasmd query wasm contract-state smart <PLANET_REGISTRY_ADDRESS> \
  '{"owner":{}}'

# Register a device
wasmd tx wasm execute <PLANET_REGISTRY_ADDRESS> \
  '{"register_planet":{"device_id":"planet-01","wallet":"galaxy1wallet..."}}' \
  --from validator \
  --chain-id galaxy-1 \
  -y -o json
```

## Webhook Integration Example

### Register Your Endpoint

```bash
curl -X POST http://localhost:8500/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme-corp",
    "target_url": "https://webhook.acme.com/galaxy-events",
    "enabled": true
  }'
```

### Webhook Payload Format

Events are delivered as:

```json
{
  "tenant_id": "acme-corp",
  "source": "galaxy-authority",
  "delivered_at": "2025-03-27T10:30:00Z",
  "event": {
    "tx_hash": "ABC123...",
    "device_id": "planet-01",
    "event_type": "vehicle_detection",
    "confidence": 0.92,
    "status": "verified",
    "metadata": {
      "location": "zone-a",
      "camera_id": "cam-001"
    }
  }
}
```

### Retry Policy

- Max retries: 4
- Backoff: `0.5s * (2^attempt)` (0.5s, 1s, 2s, 4s)
- Timeout per attempt: 5s
- Failed deliveries logged to dead-letter queue

## Compliance Policy Examples

### GDPR (EU Region)

```bash
curl -X POST http://localhost:8400/transform \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "eu-customer",
    "tenant_region": "eu",
    "event": {
      "name": "John Doe",
      "face_id": "abc123def456",
      "event_type": "person_detected",
      "confidence": 0.95
    }
  }'
```

**Response:** PII fields masked (J***e D**, a*****3d***6) + GDPR policy recorded.

### HIPAA (Health Events)

```bash
curl -X POST http://localhost:8400/transform \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "healthcare-clinic",
    "tenant_region": "us",
    "event": {
      "event_type": "patient_fall",
      "patient_id": "P12345",
      "severity": "high"
    }
  }'
```

**Response:** Event encrypted + HIPAA policy recorded in audit log.

## IBC Setup Instructions

### Connect to Osmosis Testnet

The default Hermes config connects to `osmo-test-5`. To use it:

1. **Ensure authority chain is running**
2. **Start relayer:**
   ```bash
   make ibc-up
   ```

3. **Verify channels:**
   ```bash
   docker exec galaxy-hermes-relayer hermes channel list galaxy-1 osmo-test-5
   ```

### Create IBC Channel (First Time)

If channels don't exist, create them:

```bash
docker exec galaxy-hermes-relayer hermes create channel \
  --a-chain galaxy-1 \
  --b-chain osmo-test-5 \
  --a-port transfer \
  --b-port transfer
```

### Monitor Relayer

```bash
docker logs galaxy-hermes-relayer -f
```

Look for `Packet {...}` messages indicating successful relay.

## Database Schema

### Webhook Tables
```sql
CREATE TABLE webhook_subscriptions (
  id SERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  target_url TEXT NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ
);

CREATE TABLE webhook_delivery_logs (
  id SERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  target_url TEXT NOT NULL,
  tx_hash TEXT NOT NULL,
  delivered BOOLEAN,
  attempts INTEGER,
  last_error TEXT,
  created_at TIMESTAMPTZ
);

CREATE TABLE webhook_dead_letters (
  id SERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  target_url TEXT NOT NULL,
  tx_hash TEXT NOT NULL,
  payload_json TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ
);
```

### Compliance Tables
```sql
CREATE TABLE compliance_audit_logs (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  tenant TEXT NOT NULL,
  tenant_region TEXT NOT NULL,
  policies_json TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL
);
```

All tables are created automatically on service startup.

## Troubleshooting

### Webhooks Not Delivering

1. Check service health:
   ```bash
   curl http://localhost:8500/health
   ```

2. Verify webhook is registered:
   ```bash
   curl http://localhost:8500/webhooks/subscriptions
   ```

3. Check dead-letter queue:
   ```bash
   curl http://localhost:8500/webhooks/dead-letters?limit=10
   ```

4. Ensure authority events exist:
   ```bash
   curl http://localhost:1317/galaxy/v1/events
   ```

### Compliance Engine Not Transforming

1. Confirm service is running:
   ```bash
   curl http://localhost:8400/health
   ```

2. Test with simple event:
   ```bash
   curl -X POST http://localhost:8400/transform \
     -H "Content-Type: application/json" \
     -d '{"tenant":"test","tenant_region":"eu","event":{"name":"Test"}}'
   ```

3. Check audit logs:
   ```bash
   curl http://localhost:8400/audit/recent?limit=5
   ```

### Authority Chain Not Processing Events

1. Verify authority is synced:
   ```bash
   curl http://localhost:1317/cosmos/base/tendermint/v1beta1/blocks/latest | jq .block.header.height
   ```

2. Check for event submissions in logs:
   ```bash
   docker logs galaxy-authority-chain | grep "submit_event"
   ```

3. Query stored events:
   ```bash
   curl http://localhost:1317/galaxy/v1/events
   ```

### IBC Relayer Issues

1. Verify config syntax:
   ```bash
   docker exec galaxy-hermes-relayer hermes config validate
   ```

2. Check chain connectivity:
   ```bash
   docker exec galaxy-hermes-relayer hermes query client state galaxy-1 07-tendermint-0
   ```

3. Monitor packet relay:
   ```bash
   docker logs galaxy-hermes-relayer -f | grep Packet
   ```

## Next Steps

1. **Deploy contracts** to a testnet:
   ```bash
   make contracts-test  # Verify tests pass first
   bash economic-layer/scripts/deploy_contracts.sh
   ```

2. **Integrate webhooks** with your backend:
   ```bash
   POST /webhooks/register with your tenant webhook URL
   ```

3. **Run compliance policies** as middleware in gateway or authority:
   - Compliance engine already runs as microservice
   - Can be called by other services via REST

4. **Set up IBC relayer** for cross-chain event distribution:
   ```bash
   make ibc-up
   ```

5. **Monitor and scale**:
   - Watch `docker logs` for errors
   - Scale services with `docker-compose up --scale`
   - Use Prometheus/Grafana for observability

## Commands Reference

```bash
# Setup and deployment
make setup                    # Install dependencies
make swarm-certs             # Generate TLS certs
make swarm-up                # Start all Phase V services
make swarm-down              # Stop all services

# Testing and validation
make test                    # Run Phase V integration tests
make phase-v-test            # Same as `make test`
make contracts-test          # Run CosmWasm unit tests
make chain-unit-test         # Run authority-chain unit tests

# Development
make logs                    # Stream logs from all services
make clean                   # Stop + remove volumes
make rebuild                 # Full rebuild from scratch

# Database / Tools
make db                      # Connect to PostgreSQL CLI
make redis                   # Connect to Redis CLI

# Advanced
make ibc-up                  # Start IBC relayer (Hermes)
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review service logs: `make logs`
3. Verify all services are healthy: `curl http://localhost:{8400,8500,8300,8200,8100}/health`
4. Test endpoints directly with `curl` or Postman

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
