# LLM Integration Guide – Galaxy MVP

## Overview

This document explains how to integrate and use the LLM service in the Enhanced Autonomous Cognitive Galaxy v2.0. The LLM service wraps a locally-running Ollama instance (with DeepSeek 6.7B model) to provide:

1. **AI-powered event verification** – enhances the AI verifier in the authority-chain
2. **Chat assistant** – provides a chat interface in the dashboard for domain questions
3. **Fallback resilience** – if the LLM service is unavailable, the system gracefully degrades to threshold-based verification

---

## Architecture

### Components

- **LLM Service** (`llm-service/`)
  - FastAPI application that wraps Ollama API
  - Exposes `/analyze_event` (for authority-chain) and `/chat` (for dashboard) endpoints
  - Runs on port `8600`
  - Uses environment variables for configuration

- **Ollama** (external, on host or in container)
  - Runs a DeepSeek 6.7B model
  - Default API endpoint: `http://localhost:11434`
  - Models: `deepseek-llm:6.7b` or `deepseek-coder:6.7b`

- **Authority-chain Gateway** (`authority-chain/gateway/main.py`)
  - Calls LLM service to analyze events during submission
  - Falls back to confidence-threshold logic if LLM is unavailable
  - Stores LLM verdict and reasoning in event document

- **Dashboard Frontend** (`frontend/Dashboard.js`)
  - Includes a chat widget that calls `/chat` endpoint
  - Displays messages from DeepSeek in real-time
  - Shows LLM service status in logs

### Data Flow

```
Event Submission (REST/gRPC)
    ↓
Authority-chain Gateway validates event
    ↓
Calls LLM Service: POST /analyze_event
    ↓
LLM Service queries Ollama at OLLAMA_URL
    ↓
Ollama inference (DeepSeek model) → verdict
    ↓
LLM Service returns {verdict: "genuine"/"suspicious", confidence, reasoning}
    ↓
Authority-chain updates event status based on verdict
    ↓
Event stored with llm_verdict and llm_analysis
```

---

## Prerequisites

### 1. Ollama Installation

Ollama must be installed and running **before** starting the Galaxy services.

#### Option A: Install Ollama Standalone (Docker Desktop / macOS / Windows)

```bash
# Download and install from https://ollama.ai
# Or use package manager:
brew install ollama  # macOS
# Or on Linux:
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Option B: Run Ollama as Docker Container (Linux)

If running on Linux and want Ollama in a container:

```bash
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama:latest
```

Then update the docker-compose.yml:
- Change `OLLAMA_URL` in `llm-service` from `http://host.docker.internal:11434` to `http://ollama:11434`
- Add a `depends_on` clause to `llm-service`

### 2. Pull the DeepSeek Model

After Ollama is running, pull the model:

```bash
ollama pull deepseek-llm:6.7b
# or
ollama pull deepseek-coder:6.7b
```

To verify the model is available:

```bash
ollama list
# Expected output:
# NAME                 ID              SIZE      MODIFIED
# deepseek-llm:6.7b    b8dff040e897    3.8 GB    10 seconds ago
```

---

## Configuration

### Environment Variables

#### For `llm-service` (in docker-compose.yml)

| Variable | Default | Notes |
|----------|---------|-------|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama API endpoint. Use `http://ollama:11434` if Ollama is in a container. For Linux host, use `http://172.17.0.1:11434`. |
| `OLLAMA_MODEL` | `deepseek-llm:6.7b` | Model name. Must match a model pulled into Ollama. |
| `OLLAMA_TIMEOUT` | `60` | Timeout (seconds) for Ollama API calls. Increase if inference is slow. |
| `LLM_ENABLED` | `true` | Set to `false` to disable LLM (fallback to confidence threshold). |
| `LLM_PORT` | `8600` | Port for FastAPI server. |
| `LLM_HOST` | `0.0.0.0` | Bind address. |
| `LOG_LEVEL` | `INFO` | Logging level (INFO, DEBUG, WARNING, ERROR). |

#### For `authority-chain` (in docker-compose.yml)

| Variable | Default | Notes |
|----------|---------|-------|
| `LLM_SERVICE_URL` | `http://llm-service:8600` | URL of the LLM service. Leave empty to disable LLM integration. |
| `LLM_TIMEOUT` | `30` | Timeout (seconds) for LLM service calls. |

### Choosing OLLAMA_URL Based on Environment

- **Docker Desktop (macOS / Windows):**
  - Use `http://host.docker.internal:11434`
  - Ollama runs on the host and is accessible via this special DNS name

- **Linux with Ollama on Host:**
  - Use `http://172.17.0.1:11434`
  - `172.17.0.1` is the default gateway IP inside Docker containers on Linux
  - Requires `--network host` or explicit port mapping

- **Ollama in Docker Container (same network):**
  - Run: `docker run -d --name ollama --network galaxy-net -p 11434:11434 ollama/ollama`
  - Use `http://ollama:11434` in docker-compose.yml (service name resolution)

---

## Running the System

### Step 1: Start Ollama

```bash
# If installed locally:
ollama serve

# If in Docker:
docker run -d --name ollama -p 11434:11434 ollama/ollama
# Then pull the model:
docker exec ollama ollama pull deepseek-llm:6.7b
```

### Step 2: Start Galaxy with Docker Compose

```bash
cd /path/to/mvp
docker-compose up -d

# Check that llm-service is running:
docker-compose logs llm-service
# Expected: "Starting LLM service on 0.0.0.0:8600"

# Verify health:
curl http://localhost:8600/health
# Expected response:
{
  "status": "ok",
  "service": "llm-service",
  "llm_enabled": true,
  "ollama_url": "http://host.docker.internal:11434",
  "ollama_model": "deepseek-llm:6.7b",
  "ollama_available": true
}
```

### Step 3: Test Event Verification via Authority-chain

```bash
curl -X POST http://localhost:1317/galaxy/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "submitter": "test-user",
    "envelope_id": "env-001",
    "origin_peer_id": "peer-001",
    "event": {
      "device_id": "device-01",
      "event_type": "intrusion_attempt",
      "confidence": 0.65,
      "frame_hash": "abc123def456",
      "location": "entry-gate"
    }
  }'
```

Check the authority-chain logs for LLM verdict:

```bash
docker-compose logs authority-chain | grep "LLM verdict"
# Expected: "[...] LLM verdict for event env-001: suspicious (confidence: 0.45)"
```

### Step 4: Test Chat via Dashboard

1. Open the dashboard in a browser: `http://localhost:3000` (if running frontend)
2. Scroll to the "LLM Chat Assistant" section
3. Type a question, e.g., "What should I do if a device is suspicious?"
4. Submit and wait for the LLM response
5. Check the service logs:

```bash
docker-compose logs llm-service | grep "Chat request"
```

---

## Endpoints

### LLM Service

#### `POST /analyze_event`

Analyzes an event for authenticity.

**Request:**
```json
{
  "event_type": "intrusion_attempt",
  "confidence": 0.65,
  "device_id": "device-01",
  "frame_hash": "abc123",
  "location": "entry-gate",
  "context": null
}
```

**Response:**
```json
{
  "verdict": "suspicious",
  "confidence": 0.42,
  "analysis": "LLM analysis completed. Model: deepseek-llm:6.7b",
  "reasoning": "The event has low confidence and occurs late at night, which is unusual."
}
```

**Fallback (if Ollama unavailable):**
```json
{
  "verdict": "pending",
  "confidence": 0.65,
  "analysis": "LLM unavailable; used confidence threshold.",
  "reasoning": "Confidence 0.65 is below 0.80 threshold."
}
```

#### `POST /chat`

Chat endpoint for general questions.

**Request:**
```json
{
  "question": "What is event anomaly detection?",
  "context": null
}
```

**Response:**
```json
{
  "answer": "Event anomaly detection is a technique used to identify unusual patterns in data...",
  "model": "deepseek-llm:6.7b"
}
```

#### `GET /health`

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "llm-service",
  "llm_enabled": true,
  "ollama_url": "http://host.docker.internal:11434",
  "ollama_model": "deepseek-llm:6.7b",
  "ollama_available": true
}
```

---

## Troubleshooting

### "Connection refused" error

**Symptom:** Authority-chain or dashboard logs show "Failed to connect to Ollama" or "LLM service unavailable".

**Causes:**
1. Ollama is not running
2. `OLLAMA_URL` is incorrect for your environment
3. Docker container cannot reach the host

**Solution:**
```bash
# Check Ollama is running:
curl http://localhost:11434/api/tags

# For Docker Desktop, verify host.docker.internal resolves:
docker run --rm alpine nslookup host.docker.internal

# For Linux, verify the gateway IP:
docker run --rm alpine sh -c "ip route | grep default"
# Should show something like: default via 172.17.0.1

# Update docker-compose.yml accordingly
```

### "Model not found" error

**Symptom:** LLM service logs show "Error: model 'deepseek-llm:6.7b' not found".

**Solution:**
```bash
ollama pull deepseek-llm:6.7b
ollama list  # Verify it appears
```

### Slow inference

**Symptom:** LLM responses take > 60 seconds.

**Causes:**
1. Model is running on CPU (no GPU acceleration)
2. System is under heavy load
3. Model is too large for available memory

**Solutions:**
- Check GPU status: `ollama list` and monitor system resources
- Increase `OLLAMA_TIMEOUT` environment variable
- Use a smaller model (if available)
- Allocate more resources to the Ollama process

### LLM Service disabled but authority-chain still works

**Expected behavior:** If `LLM_SERVICE_URL` is empty or LLM service is down, the authority-chain uses confidence-based verification (status = "verified" if confidence ≥ 0.8).

**To disable LLM entirely:**
```yaml
# In docker-compose.yml, authority-chain section:
environment:
  LLM_SERVICE_URL: ""  # Empty = disabled
```

---

## Monitoring

### View LLM Service Logs

```bash
docker-compose logs -f llm-service
```

Look for:
- `"Calling Ollama at ..."` – successful LLM call initiation
- `"Chat request: ..."` – chat endpoint usage
- `"Failed to connect to Ollama"` – connectivity issues

### Check Event Status with LLM Verdict

```bash
# Get event details:
curl http://localhost:1317/galaxy/v1/events | jq '.events[0]'
# Look for `llm_verdict` and `llm_analysis` fields
```

### Monitor Ollama Model Performance

```bash
ollama pull deepseek-llm:6.7b  # Check model size and pull progress
ollama ps  # Show running models and memory usage
```

---

## Performance Considerations

### Inference Speed

- **DeepSeek 6.7B:** ~5–30 seconds per event analysis (depending on CPU/GPU)
- **GPU acceleration:** Reduces to ~2–5 seconds (highly recommended)

### Memory Usage

- **Ollama process:** ~6–8 GB for 6.7B model
- **LLM service:** ~100 MB (FastAPI)
- **Total:** ~7–8 GB

### Scaling Considerations

For production deployments:
- Run Ollama on a separate machine with GPU
- Use a queue (Redis/RabbitMQ) to batch LLM requests
- Cache responses for repeated event types
- Consider using a smaller model (e.g., Mistral 7B) for faster inference at the cost of accuracy

---

## Integration with Authority-chain

### Event Verification Logic

1. **Confidence check:** If confidence ≥ 0.8, initial status = "verified"
2. **LLM check (if enabled):**
   - Send event to LLM service
   - If LLM returns "suspicious", downgrade status to "pending"
   - Store `llm_verdict` and `llm_analysis` in event document
3. **Fallback:** If LLM service is unavailable, proceed with confidence check only

### Accessing LLM Verdict

Query events to see LLM verdicts:

```bash
curl http://localhost:1317/galaxy/v1/events | jq '.events[] | {
  id: .envelope_id,
  confidence: .event.confidence,
  status: .status,
  llm_verdict: .llm_verdict,
  llm_analysis: .llm_analysis
}'
```

---

## Disabling the LLM Service

If you want to run Galaxy without the LLM service:

1. **In docker-compose.yml:**
   - Comment out or remove the `llm-service` section
   - Set `LLM_SERVICE_URL: ""` in the authority-chain environment

2. **The system will still work:** Authority-chain falls back to confidence-based verification

3. **Rebuild and restart:**
   ```bash
   docker-compose up -d --remove-orphans
   ```

---

## Advanced Configuration

### Running Ollama Behind a Proxy

If Ollama is behind a firewall or reverse proxy, configure the LLC service:

```yaml
llm-service:
  environment:
    OLLAMA_URL: https://ollama.example.com:8080  # HTTPS proxy endpoint
    OLLAMA_TIMEOUT: "120"  # Increase timeout for network latency
```

### Using a Different LLM Model

To switch models (e.g., Mistral, Llama 2):

```bash
# Pull the new model:
ollama pull mistral:7b

# Update docker-compose.yml:
llm-service:
  environment:
    OLLAMA_MODEL: mistral:7b
```

The LLM service will automatically use the new model. No code changes required.

---

## Testing

### Unit Test Template

```bash
#!/bin/bash
# Test event analysis endpoint

EVENT_DATA='{
  "event_type": "intrusion_attempt",
  "confidence": 0.65,
  "device_id": "test-device",
  "frame_hash": "test-frame",
  "location": "north-gate"
}'

echo "Testing /analyze_event endpoint..."
curl -X POST http://localhost:8600/analyze_event \
  -H "Content-Type: application/json" \
  -d "$EVENT_DATA" | jq '.'

echo -e "\nTesting /chat endpoint..."
curl -X POST http://localhost:8600/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is event verification?"}' | jq '.'

echo -e "\nTesting /health endpoint..."
curl http://localhost:8600/health | jq '.'
```

---

## References

- [Ollama Documentation](https://ollama.ai)
- [DeepSeek Model Card](https://huggingface.co/deepseek-ai/deepseek-llm-7b)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Pydantic Validation](https://docs.pydantic.dev)

---

## Support

For issues or questions:
1. Check logs: `docker-compose logs llm-service`
2. Verify Ollama is running: `curl http://localhost:11434/api/tags`
3. Test connectivity from container: `docker exec galaxy-llm-service curl -v http://host.docker.internal:11434/api/tags`
4. Review this guide's troubleshooting section
