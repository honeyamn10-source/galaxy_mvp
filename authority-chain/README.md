# Constellation Authority Chain (Phase III)

This folder contains the Phase III blockchain authority layer for the Galaxy system.

Scope:
- Cosmos SDK chain app named galaxy.
- Custom module x/galaxy for event submission and validator voting.
- Optional CosmWasm contracts for registry and rewards.
- Validator-facing APIs (gRPC/REST) consumed by swarm nodes.

Note:
This repository includes module and integration scaffolding intended to be wired into a full Cosmos SDK app (galaxyd). It is structured for incremental adoption while existing Phase II components continue to run.

## Layout

- x/galaxy/types: message/state/error definitions.
- x/galaxy/keeper: keeper methods and end blocker flow.
- x/galaxy/module: app module hooks.
- proto/galaxy/tx.proto: transaction service definition for swarm clients.
- cmd/validator-gateway: optional local validator gateway process.

## Security Model

- Swarm to validator gateway: mTLS.
- Validator P2P and consensus: CometBFT secure networking.
- Event signature verification: planet public key registry.
- Incentives: reward minting to submitter for verified events.

## Chain Integration Notes

1. Wire x/galaxy module into app.go module manager.
2. Register Msg and Query services in module basics.
3. Add params and genesis defaults for voting window and min votes.
4. Configure token denom ugalaxy.
5. Expose gRPC endpoint for swarm submission path.
