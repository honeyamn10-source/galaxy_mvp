.PHONY: help setup up down logs test clean rebuild swarm-certs swarm-up swarm-down swarm-test chain-unit-test phase-v-test contracts-test ibc-up

help:
	@echo "🌌 Galaxy Event Detection System - Phase V"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup       - Install dependencies and initialize"
	@echo "  make up          - Start all services (Docker Compose)"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View authority, swarm, intelligence, webhook, compliance logs"
	@echo "  make test        - Run full integration tests (Phase V)"
	@echo "  make clean       - Stop services and remove volumes"
	@echo "  make rebuild     - Rebuild containers from scratch"
	@echo "  make swarm-certs - Generate local mTLS certs for Phase II"
	@echo "  make swarm-up    - Start authority + swarm + edge services"
	@echo "  make swarm-down  - Stop all services including swarm"
	@echo "  make swarm-test  - Run Phase V end-to-end test"
	@echo "  make contracts-test - Run CosmWasm contract unit tests"
	@echo "  make ibc-up      - Start Hermes relayer profile"
	@echo "  make db          - Connect to PostgreSQL CLI"
	@echo "  make redis       - Connect to Redis CLI"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup && make swarm-up && make test"
	@echo ""

setup:
	@echo "📦 Installing Python dependencies..."
	pip install requests
	@echo "✓ Ready!"

up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "⏳ Waiting for services to initialize..."
	sleep 5
	@echo "✓ Services running!"
	@echo ""
	@echo "📍 Access points:"
	@echo "  Authority REST: http://localhost:1317"
	@echo "  Authority WS: ws://localhost:26657/websocket"
	@echo "  Edge API: http://localhost:8100"
	@echo ""

down:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✓ Stopped"

logs:
	docker-compose logs -f authority-chain swarm-node-1 swarm-node-2 edge-planet fl-aggregator predictive-service webhook-service compliance-engine

test:
	@echo "🧪 Running Phase V integration tests..."
	python3 test-phase-v.py

phase-v-test: test

swarm-certs:
	@echo "🔐 Generating Phase II dev certificates..."
	bash infra/certs/generate-dev-certs.sh
	@echo "✓ Certificates ready in infra/certs/dev"

swarm-up: swarm-certs
	@echo "🚀 Starting full Phase V stack..."
	docker-compose up -d --build
	@echo "✓ Phase V services starting"

swarm-down:
	@echo "🛑 Stopping Phase V stack..."
	docker-compose down
	@echo "✓ Stopped"

swarm-test: swarm-up
	@echo "🧪 Running Phase V end-to-end tests..."
	python3 test-phase-v.py

contracts-test:
	@echo "🧪 Running CosmWasm contract tests..."
	bash economic-layer/scripts/run_contract_tests.sh

ibc-up:
	@echo "🌉 Starting Hermes relayer profile..."
	docker-compose --profile ibc up -d hermes-relayer

chain-unit-test:
	@echo "🧪 Running authority-chain unit tests..."
	cd authority-chain && go test ./...

clean:
	@echo "🧹 Cleaning up (removing volumes)..."
	docker-compose down -v
	@echo "✓ Cleaned"

rebuild:
	@echo "🔨 Rebuilding from scratch..."
	docker-compose down -v
	docker-compose up -d --build
	@echo "✓ Rebuilt"

db:
	docker exec -it galaxy-db psql -U postgres -d galaxy

redis:
	docker exec -it galaxy-redis redis-cli

ps:
	docker-compose ps

health:
	curl -s http://localhost:1317/health

docs:
	@echo "📚 Authority endpoints"
	@echo "Visit: http://localhost:1317/cosmos/tx/v1beta1/txs"
