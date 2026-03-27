# Phase III Setup - Constellation Authority Layer

## Objective

Phase III replaces centralized verification with the Constellation authority layer.

Flow:

Edge Planet -> Swarm Mesh -> Validator Authority -> Chain Events -> Dashboard

## What Is Included

- Authority chain module scaffold in authority-chain/x/galaxy.
- Native galaxyd binary in authority-chain/cmd/galaxyd.
- Swarm nodes configured to submit events to validators over gRPC.
- Dashboard capable of Cosmos-style REST and Tendermint-like WebSocket updates.

## Start Phase III Stack

1. Generate certificates:

make swarm-certs

2. Start services:

make swarm-up

3. Run integration test:

make test

4. Run authority module unit tests:

cd authority-chain && go test ./...

## Endpoints

- Authority health: http://localhost:1317/health
- Authority tx query: http://localhost:1317/cosmos/tx/v1beta1/txs
- Authority event query: http://localhost:1317/galaxy/v1/events
- Authority gRPC submit: localhost:9090
	- /galaxy.galaxy.Msg/SubmitEvent
	- /galaxy.galaxy.Msg/VoteEvent
- Authority websocket: ws://localhost:26657/websocket
- Edge simulator: http://localhost:8100

## Swarm Forwarding Modes

Environment variable on swarm nodes:

- SWARM_FORWARD_MODE=backend-http: forward to legacy backend.
- SWARM_FORWARD_MODE=validator-rest: forward to authority validator endpoint.
- SWARM_FORWARD_MODE=validator-grpc: submit to validator gRPC endpoint.

Phase III default in compose is validator-grpc.

Compose service name:

- authority-chain (swarm target: VALIDATOR_GRPC_ADDR=authority-chain:9090)

## Dashboard Usage

The dashboard now supports two sources:

- Cosmos Source: reads from authority chain endpoints.
- Legacy Backend Source: fallback for compatibility.

Open dashboard and choose Cosmos Source for Phase III.

## Production Notes

- Wire x/galaxy module into full Cosmos SDK app manager and protobuf tx pipeline.
- Enable validator key management and real tx signing from swarm submitters.
- Add chain indexer to persist hot/warm analytics into Redis and TimescaleDB.

## Troubleshooting

If edge publish works but no authority events appear:

- Check swarm forward mode in logs.
- Verify VALIDATOR_GRPC_ADDR resolves from swarm containers.
- Check authority logs for malformed payloads.

If local checks cannot run:

- Install Docker and Docker Compose to run the stack.
- Install Go to run authority and swarm unit/build checks.

If dashboard has no live updates:

- Confirm ws://localhost:26657/websocket is reachable.
- Confirm dashboard source is set to Cosmos.
- Use polling endpoint /cosmos/tx/v1beta1/txs to verify events exist.
