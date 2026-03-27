---
mode: agent
model: GPT-5.3-Codex
description: "Build Phase III Blockchain Authority with Cosmos SDK, swarm gRPC submission, compose integration, tests, and setup docs."
---

You are implementing Phase III of the Enhanced Autonomous Cognitive Galaxy v2.0.

Context:

- The system already has:
  - Edge planets (Python + ONNX) that generate events.
  - Swarm nodes (Go + libp2p) that broadcast events via GossipSub and forward them to an authority.
  - A centralized FastAPI backend that currently acts as the authority (validates events, stores in DB, streams via WebSocket).
  - A React dashboard that connects to the FastAPI backend for live events.

- The goal of Phase III is to replace the centralized FastAPI backend with a decentralized blockchain authority built with Cosmos SDK.
- The new authority will:
  - Accept event submissions from swarm nodes via gRPC.
  - Use BFT consensus (Tendermint) among validator nodes to verify events.
  - Store events immutably on-chain.
  - Reward planets with GALAXY tokens when events are verified.
  - Provide a REST API for the dashboard to query verified events.

Module to build: authority-chain
This module includes:
- A Cosmos SDK-based blockchain node (binary: galaxyd).
- A custom galaxy module that handles event submission and voting.
- Integration with the existing swarm nodes: modify swarm nodes to submit events to validators via gRPC instead of the FastAPI backend.
- A REST API (Cosmos SDK standard REST) for the dashboard, replacing old FastAPI endpoints.
- Dockerfile for the chain node.
- Updated docker-compose.yml to run the chain alongside swarm nodes (and optionally remove the FastAPI backend or keep it temporarily).
- A migration plan: the dashboard will switch to querying the blockchain.

Interface Contracts (must be strictly followed):

1. Event submission (from swarm nodes to any validator):
   - Use Cosmos SDK gRPC to broadcast a MsgSubmitEvent transaction.
   - Transaction must be signed by the planet account (the planet must have an associated account on-chain; we can register planets via a smart contract or on-chain registry).
   - Message format (protobuf) must match the galaxy module MsgSubmitEvent.

2. Event verification (validators):
   - Validators (including an AI verifier special node) can submit MsgVoteEvent transactions with a yes/no vote.
   - Voting period is defined per event (for example 1 hour).
   - After voting period, the event is marked verified if enough yes votes are collected (for example more than 2/3 of total voting power).
   - Verified events are stored permanently on-chain.

3. Token rewards:
   - When an event is verified, the planet (submitter) receives GALAXY tokens.
   - Tokens are minted from a reward pool or via inflation.
   - The reward amount should be configurable (for example 100 GALAXY per event).

4. Dashboard API:
   - Dashboard will query chain REST API.
   - For real-time updates, use Tendermint WebSocket to subscribe to new events or fallback to polling.

Coding Rules:
- All configuration via environment variables.
- No hardcoded values.
- Provide error handling and logging.
- Include health checks.
- Each component (chain node, swarm node updates) must run independently.
- Provide Dockerfile for chain node.
- Update docker-compose.yml to include chain service and adjust existing services.
- Provide a clear migration and validation path (event from edge simulator through swarm to chain and verified on-chain).

Execution instructions:
- Build this module one step at a time:
  1. Create Cosmos SDK chain skeleton using ignite or starport or manual Cosmos SDK scaffold with a galaxy module.
  2. Implement the galaxy module: messages, keeper logic, genesis, events.
  3. Write unit tests for the module.
  4. Build Dockerfile for galaxyd.
  5. Update swarm nodes to use gRPC client to submit events to chain instead of HTTP to FastAPI. Provide modified Go code.
  6. Update docker-compose.yml to include galaxyd and optionally disable FastAPI backend.
  7. Provide test script verifying flow: edge simulator -> swarm -> chain -> event stored and verified.
  8. Document changes in PHASE_III_SETUP.md.

- Stop after completing all these steps; do not move on to Phase IV or other modules.

Output:
- Provide full code for new files (galaxy module, chain app, Dockerfile, updated swarm node code, updated compose).
- Include clear instructions on how to run and test Phase III.
- Ensure all changes are compatible with existing repository structure and placed under authority-chain or cosmos-chain.
