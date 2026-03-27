# Phase II Setup - Swarm Layer and Edge Planet Simulator

## Overview

Phase II introduces a decentralized transport path:

1. Edge planets generate detection events.
2. Edge planets publish to a local swarm ingress endpoint over mTLS.
3. Swarm nodes propagate events with GossipSub over libp2p.
4. The origin swarm node forwards the event to the backend /events endpoint.
5. Backend persists and broadcasts to dashboard clients over WebSocket.

## Components Added

- edge-planet service: Python FastAPI simulator that emits events.
- swarm-node service: Go libp2p node with GossipSub, Kademlia DHT, Noise + TLS.
- infra/certs script: dev certificate generator for local mTLS.
- k8s manifests: DaemonSet and bootstrap service for swarm deployment.

## Prerequisites

- Docker and Docker Compose
- OpenSSL
- Python 3.11+ (for local test script)

## 1. Generate Dev Certificates

Run from repository root:

```bash
make swarm-certs
```

This writes certificates to:

- infra/certs/dev/ca.crt
- infra/certs/dev/swarm-node.crt
- infra/certs/dev/swarm-node.key
- infra/certs/dev/edge-planet.crt
- infra/certs/dev/edge-planet.key

## 2. Start Phase II Stack

```bash
make swarm-up
```

Services:

- backend: http://localhost:8000
- swarm-node-1 ingress (mTLS): https://localhost:8443/ingest
- swarm-node-2 ingress (mTLS): https://localhost:8444/ingest
- edge-planet API: http://localhost:8100

## 3. Run End-to-End Swarm Test

```bash
make swarm-test
```

Test flow:

1. Creates tenant and device in backend.
2. Sends events to edge simulator (not directly to backend).
3. Edge publishes events into swarm ingress.
4. Swarm relays and forwards to backend.
5. Test verifies events are persisted in backend.

## 4. Validate Live Dashboard

1. Open dashboard (React app) and use API key from test output.
2. Confirm events appear in the table.
3. Status should show API + Live when WebSocket is connected.

## 5. Health Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8081/healthz
curl http://localhost:8082/healthz
curl http://localhost:8100/health
```

## 6. Manual Publish Through Edge

```bash
curl -X POST http://localhost:8100/emit-batch \
  -H "Content-Type: application/json" \
  -d '{
    "count": 5,
    "api_key": "gal_xxx",
    "device_id": "device-uuid",
    "interval_ms": 50
  }'
```

## Environment Variables

### Swarm Node

- SWARM_NODE_NAME: node identifier for logs.
- SWARM_IDENTITY_SEED: deterministic peer identity seed.
- SWARM_P2P_PORT: libp2p TCP port.
- SWARM_BOOTSTRAP_PEERS: comma-separated multiaddrs.
- SWARM_BOOTSTRAP_SEEDS: seed-based bootstrap specs, format seed@host:port.
- SWARM_RENDEZVOUS: DHT rendezvous namespace.
- BACKEND_EVENTS_URL: backend ingestion endpoint.
- SWARM_TLS_CERT: server cert path.
- SWARM_TLS_KEY: server key path.
- SWARM_CLIENT_CA: trusted CA for client cert verification.

### Edge Planet

- SWARM_INGEST_URL: swarm ingress endpoint.
- EDGE_TENANT_API_KEY: default tenant API key.
- EDGE_DEVICE_ID: default device id.
- EDGE_CA_CERT: trusted CA path.
- EDGE_CLIENT_CERT: edge client cert path.
- EDGE_CLIENT_KEY: edge private key path.

## Kubernetes Deployment Notes

Manifests are in swarm-node/k8s:

- bootstrap-service.yaml
- daemonset.yaml

Before applying:

1. Create namespace galaxy.
2. Create TLS secret swarm-node-tls with CA and key material.
3. Set image in daemonset to your registry.

Example:

```bash
kubectl create namespace galaxy
kubectl -n galaxy create secret generic swarm-node-tls \
  --from-file=ca.crt=infra/certs/dev/ca.crt \
  --from-file=swarm-node.crt=infra/certs/dev/swarm-node.crt \
  --from-file=swarm-node.key=infra/certs/dev/swarm-node.key
kubectl apply -f swarm-node/k8s/bootstrap-service.yaml
kubectl apply -f swarm-node/k8s/daemonset.yaml
```

## Security Notes

- Edge to swarm ingress is enforced with TLS 1.3 and client certificate verification.
- Swarm peer links use libp2p encrypted channels (Noise and TLS).
- For production: move cert issuance to cert-manager or Vault and rotate keys periodically.

## Troubleshooting

If swarm nodes fail to connect:

- Check SWARM_BOOTSTRAP_SEEDS and container DNS names.
- Verify both nodes share SWARM_RENDEZVOUS value.
- Inspect logs: docker-compose logs -f swarm-node-1 swarm-node-2.

If edge publish fails with TLS errors:

- Re-generate certs with make swarm-certs.
- Verify files exist in infra/certs/dev.
- Check CN/SAN values include service DNS names.

If backend receives no events:

- Confirm BACKEND_EVENTS_URL resolves to authority:8000/events from swarm container.
- Check API key and device id used by edge simulator.
- Inspect backend logs: docker-compose logs -f backend.
