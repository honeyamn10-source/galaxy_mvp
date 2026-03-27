# Phase IV Setup - Intelligence Layer

## Objective

Phase IV adds federated learning and predictive analytics to the existing authority flow.

Flow:

Edge Planet -> Swarm Mesh -> Authority Chain -> Intelligence Layer -> Predictive Alerts

## What Is Included

- FL aggregator service in intelligence-layer/fl-aggregator.
- Edge FL client loop integrated into edge-planet.
- Predictive analytics service in intelligence-layer/predictive-service.
- Swarm dual-topic ingestion for events and prediction alerts.
- Dashboard prediction panel for high-risk alert visibility.

## Start Phase IV Stack

1. Generate certificates:

make swarm-certs

2. Build and start all services:

make swarm-up

3. Run Phase IV integration test:

make test

## Endpoints

- Authority health: http://localhost:1317/health
- Authority event query: http://localhost:1317/galaxy/v1/events
- Edge simulator health: http://localhost:8100/health
- Edge FL status: http://localhost:8100/fl/status
- FL aggregator health: http://localhost:8200/health
- FL global model: http://localhost:8200/fl/model/latest
- Predictive health: http://localhost:8300/health
- Predictive latest alerts: http://localhost:8300/predictions/latest
- Swarm event ingest (mTLS): https://localhost:8443/ingest
- Swarm prediction ingest (mTLS): https://localhost:8443/ingest-prediction

## Configuration

### FL Aggregator

- FL_DATABASE_URL: PostgreSQL connection string.
- FL_MODEL_DIR: on-disk global model path.
- FL_MODEL_SIZE: expected model vector size (default 32).
- FL_MIN_UPDATES_FOR_AGG: minimum pending updates before aggregation.

### Edge FL Client

- FL_ENABLED: enable FL background loop.
- FL_AGGREGATOR_URL: base URL for FL aggregator.
- FL_CLIENT_ID: edge participant identifier.
- FL_SYNC_INTERVAL_SECONDS: periodic push/pull interval.

### Predictive Service

- PRED_AUTHORITY_URL: authority event source.
- PRED_SWARM_PUBLISH_URL: swarm prediction ingress URL.
- PRED_RISK_THRESHOLD: threshold for high-risk classification.
- OPENWEATHER_API_KEY: optional weather enrichment key.

## Integration Test Coverage

The test script test-phase1.py validates:

- authority, edge, FL aggregator, and predictive service health,
- edge event publication through swarm to authority,
- FL train-once update roundtrip,
- predictive run-once generation and fetch of alert outputs.

## Troubleshooting

If predictions are not visible:

- Confirm predictive service health and logs.
- Verify swarm endpoint /ingest-prediction is reachable from predictive container.
- Check authority /galaxy/v1/events for prediction_alert entries.

If FL does not progress:

- Verify edge FL is enabled via /fl/status.
- Check FL aggregator DB connectivity and model dimension settings.
- Ensure FL_MODEL_DIM (edge) equals FL_MODEL_SIZE (aggregator).

If local checks cannot run:

- Install Docker and Docker Compose for full stack validation.
- Install Go to compile swarm-node and authority-chain locally.
