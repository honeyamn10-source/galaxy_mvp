# LLM Service Integration – Quick Start Guide

For full platform architecture and phase-by-phase operations, see [README.md](../README.md).

## Overview

The Galaxy MVP now includes an **LLM Service** that enhances event verification using a locally-running DeepSeek 6.7B model via Ollama. This guide provides a quick start before reading the full documentation.

---

## Prerequisites

1. **Ollama installed** on your host machine (or as a Docker container)
2. **DeepSeek model pulled** (`ollama pull deepseek-llm:6.7b`)
3. **Docker and Docker Compose** available

---

## Quick Start (5 minutes)

### Step 1: Install and Start Ollama

```bash
# If Ollama is not installed, install it from https://ollama.ai
# Then start Ollama:
ollama serve
# In another terminal, pull the model:
ollama pull deepseek-llm:6.7b
```

### Step 2: Start the Galaxy Stack

```bash
cd /home/honey/mvp

# Start all services including LLM:
docker-compose up -d

# Or use the Makefile:
make ollama-up  # Start Ollama (if on same machine)
make swarm-up   # Start Galaxy services
```

### Step 3: Verify Everything is Running

```bash
# Test the LLM service:
bash test-llm.sh

# Or manually test:
curl http://localhost:8600/health | jq '.'
```

### Step 4: Test Event Analysis

```bash
# Submit an event to the authority-chain:
curl -X POST http://localhost:1317/galaxy/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "submitter": "test-user",
    "envelope_id": "env-test-001",
    "origin_peer_id": "peer-001",
    "event": {
      "device_id": "device-01",
      "event_type": "intrusion_attempt",
      "confidence": 0.65,
      "frame_hash": "test123",
      "location": "entry-gate"
    }
  }'

# View event details (including LLM verdict):
curl http://localhost:1317/galaxy/v1/events | jq '.events[0]'
```

### Step 5: Try the Chat Widget (Optional)

```bash
# If the dashboard is running, open http://localhost:3000
# Scroll to "LLM Chat Assistant" section
# Ask a question like: "What is event verification?"
# Wait for the response from DeepSeek

# Or test via curl:
curl -X POST http://localhost:8600/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is event verification?"}'
```

---

## What Changed

### New Files Created

1. **`llm-service/`** – Complete LLM service implementation
   - `main.py` – FastAPI app with 3 endpoints
   - `requirements.txt` – Dependencies
   - `Dockerfile` – Container definition

2. **`test-llm.sh`** – Comprehensive test suite for LLM integration

3. **`docs/LLM_INTEGRATION.md`** – Complete documentation

### Modified Files

1. **`authority-chain/gateway/main.py`**
   - Added `call_llm_verifier()` function
   - Integrated LLM call into `ingest_submission()`
   - Enhanced `/health` endpoint with LLM status
   - Added `requests` import and LLM env var configuration

2. **`docker-compose.yml`**
   - Added `llm-service` container definition
   - Added `LLM_SERVICE_URL` and `LLM_TIMEOUT` to authority-chain

3. **`frontend/Dashboard.js`**
   - Added chat widget state
   - Added `handleChatSend()` function
   - Added chat UI section with input and message display

4. **`Makefile`**
   - Added `ollama-up`, `ollama-down`, `llm-up`, `llm-down`, `test-llm` targets
   - Updated help text with new LLM commands

---

## How It Works

### Event Verification Flow

```
1. Event submitted to authority-chain REST API
2. Gateway validates event structure
3. Gateway calls LLM service: POST /analyze_event
4. LLM queries Ollama for inference
5. DeepSeek returns verdict (genuine/suspicious)
6. Event status updated based on verdict
7. Store event with llm_verdict and llm_analysis
```

### Chat Widget Flow

```
1. User types question in dashboard chat widget
2. Dashboard sends POST /chat to llm-service
3. LLM service calls Ollama
4. DeepSeek generates response
5. Response displayed in chat widget
```

### Fallback Behavior

If LLM service is unavailable:
- Authority-chain reverts to **confidence-based verification** (confidence ≥ 0.8 = verified)
- Chat widget shows error message
- No events are lost or rejected

---

## Makefile Commands

```bash
# LLM Infrastructure
make ollama-up       # Start Ollama and pull model
make ollama-down     # Stop Ollama
make llm-up          # Start only LLM service (requires Ollama running)
make llm-down        # Stop LLM service
make test-llm        # Run comprehensive test suite

# Standard Galaxy commands
make swarm-up        # Start all Galaxy services
make up              # Start all services
make down            # Stop all services
make logs            # View logs
make test            # Run integration tests
```

---

## Common Issues & Solutions

### "Connection refused" when testing

**Cause:** Ollama is not running or not accessible

**Solution:**
```bash
# Verify Ollama is running:
curl http://localhost:11434/api/tags

# If not running, start it:
ollama serve
```

### "Model not found" in logs

**Cause:** DeepSeek model not pulled

**Solution:**
```bash
ollama pull deepseek-llm:6.7b
ollama list  # Verify
```

### LLM service slow or timing out

**Cause:** Inference is slow (depends on CPU/GPU)

**Solutions:**
- Increase `OLLAMA_TIMEOUT` in docker-compose.yml (default 60s)
- Check if GPU is available: `nvidia-smi` or `ollama ps`
- Consider running Ollama on a separate machine with GPU

### LLM service not reachable from authority-chain

**Cause:** Docker network issue or service not started

**Solution:**
```bash
# Check if llm-service is running:
docker-compose logs llm-service

# Restart the service:
docker-compose restart llm-service

# Verify connectivity from authority-chain:
docker exec galaxy-authority-chain curl http://llm-service:8600/health
```

---

## Configuration Options

### To disable LLM service entirely:

```yaml
# In docker-compose.yml, authority-chain section:
environment:
  LLM_SERVICE_URL: ""  # Empty string disables LLM
```

### To use a different model:

```bash
# 1. Pull the new model:
ollama pull mistral:7b

# 2. Update docker-compose.yml:
llm-service:
  environment:
    OLLAMA_MODEL: mistral:7b  # Change this line
```

### For Docker Desktop on Mac/Windows:

```yaml
# OLLAMA_URL in docker-compose.yml should be:
OLLAMA_URL: http://host.docker.internal:11434
```

### For Docker on Linux with host Ollama:

```yaml
# OLLAMA_URL should be:
OLLAMA_URL: http://172.17.0.1:11434
# (or whatever your docker0 bridge IP is)
```

---

## Next Steps

1. **Read the full documentation:** [docs/LLM_INTEGRATION.md](docs/LLM_INTEGRATION.md)
2. **Monitor logs:** `docker-compose logs -f llm-service`
3. **Test in production:** Submit real events and verify verdicts
4. **Customize prompts:** Edit the prompt in `llm-service/main.py` for your domain
5. **Integrate with external systems:** The `/chat` endpoint can be called from any client

---

## Support

- Full API documentation: See `openapi.json` at `http://localhost:8600/openapi.json` (when running)
- Detailed troubleshooting: [docs/LLM_INTEGRATION.md - Troubleshooting](docs/LLM_INTEGRATION.md#troubleshooting)
- Test script: Run `bash test-llm.sh` for automatic diagnostics
