<p align="center">
  <img src="docs/assets/logo.svg" alt="Galaxy MVP — autonomous edge-intelligence platform" width="100%" />
</p>

<p align="center">
  <img src="docs/logo/logo.png" width="96" height="96" alt="Galaxy logo mark" />
</p>



<p align="center">
  <b>Autonomous edge-intelligence platform</b>
  <br />
  <em>Decentralized swarm compute with an AI authority chain — edge inference, federated learning, and tamper-evident event verification.</em>
</p>
Galaxy</h1>

<p align="center">
  <img src="docs/logo/logo.png" width="168" height="168" alt="Galaxy — six edge swarm nodes orbiting an authority-chain nucleus" />
</p>

<p align="center">
  <b>Enhanced Autonomous Cognitive Galaxy</b>
  <br />
  <em>A decentralized AI event-detection platform — edge inference, secure swarm propagation, blockchain authority, and federated intelligence.</em>
</p>

<p align="center">
  <a href="https://github.com/honeyamn10-source/galaxy_mvp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/honeyamn10-source/galaxy_mvp/releases"><img src="https://img.shields.io/badge/version-2.0-blue.svg" alt="Version: 2.0"></a>
  <a href="https://github.com/honeyamn10-source/galaxy_mvp/actions/workflows/ci.yml"><img src="https://github.com/honeyamn10-source/galaxy_mvp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/honeyamn10-source/galaxy_mvp/actions/workflows/security-scan.yml"><img src="https://github.com/honeyamn10-source/galaxy_mvp/actions/workflows/security-scan.yml/badge.svg" alt="Security"></a>
  <a href="https://github.com/honeyamn10-source/galaxy_mvp"><img src="https://img.shields.io/badge/stage-development-important.svg" alt="Stage: Development"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-3776AB.svg" alt="Python 3.11+"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/docker-compose-2496ED.svg" alt="Docker Compose"></a>
</p>

---

**Galaxy** is a decentralized AI event-detection platform built for environments that need edge inference at the source, tamper-evident event verification, and privacy-preserving learning — without handing data to a central party. Events are detected at the edge, propagated through an authenticated peer-to-peer swarm, verified by a blockchain-backed authority chain, and analyzed by a federated intelligence layer.

> **Review status:** This is a development repository. Phase labels describe the existing implementation and notes, not a production certification. Validate deployment, security, and integrations before any release.

## 🚀 What Galaxy delivers

| Capability | Description |
| --- | --- |
| 🛰️ **Edge AI detection** | Multi-tenant event ingestion with YOLO/agent inference at the source |
| 🔐 **Secure swarm mesh** | Peer-to-peer propagation over libp2p with mTLS and validator forwarding |
| ⛓️ **Blockchain authority** | Cosmos-style authority node with event verification, voting, and reward logic |
| 🧠 **Federated intelligence** | FL aggregation and a predictive risk analytics service |
| 📋 **Expansion & economy** | Compliance transformation, webhooks, CosmWasm contracts, IBC relay profile |
| 🛡️ **Hardened delivery** | Kubernetes manifests, monitoring, backup/restore, and CI/CD |
| 🤖 **Optional local LLM** | DeepSeek augmentation (via Ollama) for nuanced verification and chat |

## 🖼️ Gallery & screenshots

Real, loopback-only captures from `docs/screenshots/` — the landing page and dashboard preview, served strictly on `127.0.0.1` and rendered headlessly. Nothing here listens beyond loopback.

<p align="center">
  <img src="docs/screenshots/landing-hero.png" alt="Galaxy landing page — hero render over loopback" />
</p>

See `docs/screenshots/` for the full gallery, `docs/diagrams/` for the architecture diagram (SVG + PNG), and `docs/logo/` for the logo source.

## 🛡️ Design & team structure

Decisions are tracked as **Architecture Decision Records** in `docs/decisions/` — including **[ADR-0005 — many-agent team collaboration](docs/decisions/0005-many-agent-team-collaboration.md)**: Galaxy behaves like a *team of specialist agents* (a permission-led crew), with a team-lead gating approvals, and **no single role granted "do anything over the internet" or surveillance access**. Universal across fields means more governed, field-specialist roles — never fewer guardrails.

## 🧭 Architecture

```mermaid
flowchart LR
  EP[Edge Planet] --> SN1[Swarm Node 1]
  SN1 --> SN2[Swarm Node 2]
  SN1 --> AC[Authority Chain Gateway]
  AC --> DB[PostgreSQL]
  AC --> RD[Redis]
  AC --> CE[Compliance Engine]
  CE --> WS[Webhook Service]
  AC --> FL[FL Aggregator]
  AC --> PR[Predictive Service]
  AC --> LLM[LLM Service]
  LLM --> OLL[Ollama DeepSeek]
  FE[Dashboard] --> AC
  FE --> PR
  FE --> LLM
```

## 🗺️ System phases

| Phase | Name | Status | Core outcome |
| --- | --- | --- | --- |
| I | Edge & Backend | ✅ | FastAPI backend, dashboard, PostgreSQL, Redis, edge ingestion |
| II | Swarm Mesh | ✅ | libp2p event mesh with mTLS and validator forwarding |
| III | Blockchain Authority | ✅ | Cosmos-like authority node and event voting surfaces |
| IV | Intelligence | ✅ | FL aggregator and predictive risk service |
| V | Expansion & Economy | ✅ | Compliance engine, webhooks, CosmWasm contracts, Hermes profile |
| VI | Production Hardening | ✅ | Kubernetes manifests, monitoring stack, CI/CD, backups |
| LLM | DeepSeek Integration | ✅ | Ollama-backed analysis and chat endpoints |

## ⚡ Quickstart (Docker Compose)

### Prerequisites

- Docker Engine + Docker Compose plugin
- GNU Make
- Python 3.11+ (optional tests)
- `jq` (recommended)
- **Optional LLM path:** Ollama with a DeepSeek model

### Start the core stack

```bash
make swarm-up
```

or equivalently:

```bash
docker-compose up -d --build
```

### Verify health

```bash
make health
```

Each service exposes a health endpoint on its own port (`8100`–`8600`).

### Run integration tests

```bash
make test
```

### Run the demo stack

```bash
./demo.sh
```

Demo URLs:

| Service | URL |
| --- | --- |
| Dashboard | http://localhost:8000 |
| Landing page | http://localhost:8080 |
| Authority health | http://localhost:1317/health |
| Authority events | http://localhost:1317/galaxy/v1/events |

For a health-only pass with auto-restart of unhealthy services:

```bash
./preflight.sh
```

### One-click interactive installer

```bash
bash install-galaxy.sh
```

Prompts: Edge API key, optional RTSP URL, compliance region.

## ✅ Deploying to Kubernetes

See [PHASE_VI_SETUP.md](PHASE_VI_SETUP.md) and the manifests under [k8s](k8s).

```bash
kubectl apply -f k8s/namespaces.yaml
kubectl apply -f k8s/configmaps.yaml
kubectl apply -f k8s/secrets.yaml.template
kubectl apply -f k8s/deployments/postgres-redis.yaml
kubectl apply -f k8s/deployments/authority-chain.yaml
kubectl apply -f k8s/deployments/swarm-node.yaml
kubectl apply -f k8s/deployments/intelligence-layer.yaml
kubectl apply -f k8s/deployments/expansion-layer.yaml
kubectl apply -f k8s/deployments/dashboard.yaml
kubectl apply -f k8s/services/services.yaml
kubectl apply -f k8s/network-policies.yaml
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/grafana.yaml
kubectl apply -f k8s/ingress.yaml
```

## 🤖 Optional local LLM

Start Ollama and pull/verify the model:

```bash
make ollama-up
make llm-up
make test-llm
```

> Linux note: if Ollama runs on the host and `host.docker.internal` is unavailable, use the `172.17.0.1` bridge gateway or run Ollama as a peer container.

## 📁 Repository layout

```
galaxy_mvp/
├── backend/               # Core ingestion/backend services
├── edge-planet/           # Edge inference (YOLO/agent) service
├── swarm-node/            # libp2p swarm mesh with mTLS
├── authority-chain/       # Cosmos-style authority + voting
├── intelligence-layer/    # FL aggregator + predictive service
├── expansion-layer/       # Compliance engine + webhooks
├── economic-layer/        # CosmWasm contracts + economy
├── llm-service/           # Ollama-backed analysis and chat
├── auth-service/          # Authentication
├── workers/               # Background workers
├── frontend/              # Dashboard
├── portfolio/             # Landing/portfolio page
├── k8s/                   # Kubernetes deployment manifests
├── docs/                  # LLM integration guides
├── models/                # Mounted model artifacts
├── scripts/               # Backup/restore and tooling
└── .github/workflows/     # CI/CD and security scanning
```

## 🔧 Configuration

All runtime configuration is environment-driven. Reference: [docker-compose.yml](docker-compose.yml) and [k8s/configmaps.yaml](k8s/configmaps.yaml).

### Core services

| Service | Key environment variables |
| --- | --- |
| authority-chain | `CHAIN_ID`, `CHAIN_VOTE_THRESHOLD`, `CHAIN_COMPLIANCE_URL`, `LLM_SERVICE_URL`, `LLM_TIMEOUT` |
| swarm-node | `SWARM_NODE_NAME`, `SWARM_RENDEZVOUS`, `SWARM_BOOTSTRAP_SEEDS`, `VALIDATOR_GRPC_ADDR` |
| edge-planet | `SWARM_INGEST_URL`, `FL_ENABLED`, `FL_AGGREGATOR_URL`, `FL_SYNC_INTERVAL_SECONDS` |
| fl-aggregator | `FL_DATABASE_URL`, `FL_MODEL_DIR`, `FL_MIN_UPDATES_FOR_AGG` |
| predictive-service | `PRED_AUTHORITY_URL`, `PRED_SWARM_PUBLISH_URL`, `PRED_RISK_THRESHOLD` |
| compliance-engine | `COMPLIANCE_DEFAULT_REGION`, `COMPLIANCE_HIPAA_EVENT_TYPES`, `COMPLIANCE_PII_KEYS` |
| webhook-service | `WEBHOOK_DATABASE_URL`, `WEBHOOK_AUTHORITY_EVENTS_URL`, `WEBHOOK_MAX_RETRIES` |

### LLM service

| Variable | Purpose | Default |
| --- | --- | --- |
| `OLLAMA_URL` | Ollama API base URL | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | Local model tag | `deepseek-llm:6.7b` |
| `OLLAMA_TIMEOUT` | Inference timeout (s) | `60` |
| `LLM_ENABLED` | Toggle LLM behavior | `true` |
| `LLM_SERVICE_URL` | Authority gateway target | `http://llm-service:8600` |
| `LLM_TIMEOUT` | Authority→LLM timeout (s) | `30` |

## 📡 API surface

| Component | URL |
| --- | --- |
| Authority REST | `http://localhost:1317` |
| Authority WebSocket | `ws://localhost:26657/websocket` |
| Edge Planet | `http://localhost:8100` |
| FL Aggregator | `http://localhost:8200` |
| Predictive Service | `http://localhost:8300` |
| Compliance Engine | `http://localhost:8400` |
| Webhook Service | `http://localhost:8500` |
| LLM Service | `http://localhost:8600` |

## 🔄 Backup & restore

```bash
bash scripts/backup.sh
bash scripts/restore.sh /path/to/backup.tar.gz
```

## 🛡️ CI/CD & security

- CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)
- CD & Cloudflare Pages: [.github/workflows/cd.yml](.github/workflows/cd.yml) · [cloudflare-pages.yml](.github/workflows/cloudflare-pages.yml)
- Vulnerability scanning: [.github/workflows/security-scan.yml](.github/workflows/security-scan.yml)

Workflows cover linting, tests, container build validation, and vulnerability scanning. See [SECURITY.md](SECURITY.md) to report a vulnerability.

## 📖 Documentation

| Document | Covers |
| --- | --- |
| [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) | System architecture overview |
| [API_INTEGRATION.md](API_INTEGRATION.md) | API integration details |
| [PHASE_I_SETUP.md](PHASE_I_SETUP.md) — [PHASE_VI_SETUP.md](PHASE_VI_SETUP.md) | Phase-by-phase setup guides |
| [docs/LLM_INTEGRATION.md](docs/LLM_INTEGRATION.md) · [docs/LLM_QUICKSTART.md](docs/LLM_QUICKSTART.md) | LLM service integration |
| [STATUS_REPORT.md](STATUS_REPORT.md) | Development status |

## 🩺 Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `docker-compose` not found | Use `docker compose up -d` (plugin syntax) on modern Docker |
| Service unhealthy / restart loops | `make logs`, validate `docker compose config`, confirm dependency health returns 200 |
| LLM cannot reach Ollama | Verify `curl http://localhost:11434/api/tags`; set `OLLAMA_URL` per environment |
| Swarm TLS errors | `make swarm-certs && make swarm-down && make swarm-up` |
| Inconsistent PostgreSQL state | `make clean && make swarm-up` |

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first and review the [Code of Conduct](CODE_OF_CONDUCT.md).

## 📄 License

[MIT](LICENSE) © 2026 [Bittu Sharma](https://github.com/honeyamn10-source)