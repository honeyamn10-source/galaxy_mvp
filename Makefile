.PHONY: help setup up down logs test clean rebuild swarm-certs swarm-up swarm-down swarm-test chain-unit-test phase-v-test contracts-test ibc-up ollama-up ollama-down test-llm llm-up llm-down

help:
	@echo "🌌 Galaxy Event Detection System - Extended with LLM Support"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup       - Install dependencies and initialize"
	@echo "  make up          - Start all services (Docker Compose)"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View service logs"
	@echo "  make test        - Run full integration tests (Phase V)"
	@echo "  make clean       - Stop services and remove volumes"
	@echo "  make rebuild     - Rebuild containers from scratch"
	@echo "  make swarm-certs - Generate local mTLS certs for Phase II"
	@echo "  make swarm-up    - Start authority + swarm + edge services"
	@echo "  make swarm-down  - Stop all services including swarm"
	@echo "  make swarm-test  - Run Phase V end-to-end test"
	@echo "  make contracts-test - Run CosmWasm contract unit tests"
	@echo "  make ibc-up      - Start Hermes relayer profile"
	@echo ""
	@echo "LLM Service (NEW):"
	@echo "  make ollama-up   - Start Ollama service with DeepSeek model"
	@echo "  make ollama-down - Stop Ollama service"
	@echo "  make llm-up      - Start LLM service (requires Ollama)"
	@echo "  make llm-down    - Stop LLM service"
	@echo "  make test-llm    - Test LLM integration (requires all services running)"
	@echo ""
	@echo "Database:"
	@echo "  make db          - Connect to PostgreSQL CLI"
	@echo "  make redis       - Connect to Redis CLI"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup && make ollama-up && make swarm-up && make test"
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

ollama-up:
	@echo "🦙 Starting Ollama service..."
	@if command -v ollama &> /dev/null; then \
		echo "Starting Ollama locally..."; \
		ollama serve &> /tmp/ollama.log & \
		sleep 3; \
		echo "Pulling DeepSeek model (this may take a few minutes)..."; \
		ollama pull deepseek-llm:6.7b; \
		echo "✓ Ollama is ready at http://localhost:11434"; \
	else \
		echo "Ollama not installed. Install from https://ollama.ai or run:"; \
		echo "  curl -fsSL https://ollama.ai/install.sh | sh"; \
		curl http://localhost:11434/api/tags 2>/dev/null && echo "✓ But it's already running!"; \
	fi

ollama-down:
	@echo "🛑 Stopping Ollama..."
	@pkill -f "ollama serve" || echo "Ollama not running"
	@echo "✓ Ollama stopped"

llm-up:
	@echo "🤖 Starting LLM service..."
	docker-compose up -d llm-service
	@echo "⏳ Waiting for LLM service to initialize..."
	sleep 3
	@echo "✓ LLM service running at http://localhost:8600"

llm-down:
	@echo "🛑 Stopping LLM service..."
	docker-compose down llm-service
	@echo "✓ LLM service stopped"

test-llm:
	@echo "🧪 Testing LLM integration..."
	bash test-llm.sh


docs:
	@echo "📚 Authority endpoints"
	@echo "Visit: http://localhost:1317/cosmos/tx/v1beta1/txs"
