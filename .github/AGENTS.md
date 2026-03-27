# Galaxy AI Agent System

## System Context

Project Name: Enhanced Autonomous Cognitive Galaxy v2.0

Goal:
Build a decentralized AI-powered event detection and verification system with:
- Edge AI inference
- P2P swarm communication
- Multi-tenant SaaS backend and authority-chain migration path
- Real-time dashboard
- Token-based rewards

Architecture:
- Edge: Python + ONNX pipeline and simulator
- Swarm: Go + libp2p
- Backend and authority: FastAPI services and Cosmos-style authority chain scaffold
- Data: PostgreSQL + Redis
- Frontend: React

## Delivery Contract

All implementation work must follow these constraints:
- Build one module at a time.
- Keep modules independently runnable.
- Use environment variables, no hardcoded secrets.
- Include production-grade error handling and logs.
- Include Dockerfile for all new long-lived services.
- Preserve compatibility unless migration is explicitly requested.
- Do not invent libraries; use established open-source dependencies.

## Module Breakdown

Module 1: Edge Planet
- Generate and submit signed detection events.
- Support simulator path and model integration path.

Module 2: Swarm Node
- Accept edge ingress with mTLS.
- Gossip events via libp2p.
- Forward to authority endpoint according to forwarding mode.

Module 3: Authority Layer
- Accept event submission from swarm.
- Maintain immutable event flow and query endpoints.
- Expose Cosmos-compatible transaction/event surfaces.

Module 4: Dashboard
- Show event stream in near real time.
- Support source switch for migration stages.

## Interface Contract

Canonical event payload:

{
  "device_id": "string",
  "timestamp": "int",
  "event_type": "string",
  "confidence": "float",
  "frame_hash": "string",
  "signature": "string"
}

Submission behavior:
- Edge submits to swarm ingress endpoint.
- Swarm envelope includes source metadata.
- Authority stores and emits verified lifecycle events.

## Execution Rules for Agents

- Start by identifying current phase and migration state.
- Make small, testable changes with explicit file updates.
- After each module change, run syntax or static checks available in environment.
- If runtime tools are unavailable, state exactly what could not be executed.
- Always add or update setup documentation when architecture changes.

## Preferred Task Sequence

1. Edge implementation and local test.
2. Swarm integration and relay test.
3. Authority integration and event query validation.
4. Dashboard adaptation and end-to-end verification.
5. Hardening: security, scalability, observability.
