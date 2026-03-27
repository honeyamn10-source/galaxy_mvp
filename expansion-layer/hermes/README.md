# Hermes IBC Relayer (Phase V)

This configuration connects the local galaxy-1 authority chain to osmo-test-5.

## Run with Docker Compose

Set these environment variables first:

- HERMES_GALAXY_MNEMONIC
- HERMES_OSMO_MNEMONIC

Then start service:

docker-compose up -d hermes-relayer

## One-time setup (inside container)

hermes keys add --chain galaxy-1 --mnemonic-file /keys/galaxy.mnemonic
hermes keys add --chain osmo-test-5 --mnemonic-file /keys/osmo.mnemonic
hermes create client --host-chain osmo-test-5 --reference-chain galaxy-1
hermes create connection --a-chain galaxy-1 --b-chain osmo-test-5
hermes create channel --a-chain galaxy-1 --a-connection connection-0 --a-port transfer --b-port transfer --channel-version ics20-1

## Relay packets

hermes start

Note: Testnet endpoints can rotate; update config.toml if osmo-test-5 RPC endpoints change.
