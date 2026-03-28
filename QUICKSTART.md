# 🚀 Galaxy Phase I - Quick Reference

## One-Liner Setup

```bash
docker-compose up -d && python3 test-phase1.py
```

## Essential Commands

```bash
# Start everything
make up

# Run tests
make test

# View API documentation
http://localhost:8000/docs

# Check health
curl http://localhost:8000/health

# View logs
make logs

# Stop everything
make down
```

## Create Your First Tenant (2 minutes)

```bash
# Create tenant
TENANT=$(curl -s -X POST http://localhost:8000/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company", "quota_events_per_day": 10000}')

API_KEY=$(echo $TENANT | jq -r '.api_key')
echo "Your API Key: $API_KEY"

# Save for later
export API_KEY
```

## Register a Camera Device

```bash
DEVICE=$(curl -s -X POST http://localhost:8000/devices \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "device_type": "jetson",
    "location": "Entrance",
    "public_key": "test_key"
  }')

DEVICE_ID=$(echo $DEVICE | jq -r '.id')
echo "Device ID: $DEVICE_ID"
```

## Submit a Detection Event

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "'$DEVICE_ID'",
    "event_type": "fire",
    "confidence": 0.92,
    "location": "Building A, Floor 2"
  }'
```

## Query Events

```bash
# Get all events
curl -s http://localhost:8000/events \
  -H "X-API-Key: $API_KEY" | jq '.items[]'

# Filter by type
curl -s 'http://localhost:8000/events?event_type=fire' \
  -H "X-API-Key: $API_KEY" | jq '.items[]'

# Get verified only
curl -s 'http://localhost:8000/events?verified_only=true' \
  -H "X-API-Key: $API_KEY" | jq '.items[]'
```

## Tenant Info

```bash
curl -s http://localhost:8000/me \
  -H "X-API-Key: $API_KEY" | jq '.'
```

## Database Queries

```bash
# Connect
docker exec -it galaxy-db psql -U postgres -d galaxy

-- Count events
SELECT count(*) FROM events;

-- See recent events
SELECT id, event_type, confidence, verified, created_at
FROM events
ORDER BY created_at DESC
LIMIT 10;

-- Check your tenant
SELECT id, name, events_today, quota_events_per_day FROM tenants;

-- View devices
SELECT id, name, status, last_heartbeat FROM devices;
```

## Redis Real-Time Events

```bash
# Connect
docker exec -it galaxy-redis redis-cli

# Subscribe to your tenant's events
SUBSCRIBE events:your-tenant-id

# Or view all channels
PUBSUB CHANNELS
```

## Common Issues

### Backend won't start
```bash
# Rebuild
docker-compose up -d --build

# Check logs
docker-compose logs backend
```

### Port already in use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### PostgreSQL connection error
```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

### Test failures
```bash
# Make sure backend is healthy
curl http://localhost:8000/health

# Check all services are running
docker-compose ps
```

## Architecture Files

- `PHASE_I_SETUP.md` - Full setup guide
- `ARCHITECTURE_SUMMARY.md` - System design (this phase)
- `backend/main.py` - FastAPI routes
- `backend/database.py` - Data models
- `frontend/Dashboard.js` - React UI
- `docs/LLM_INTEGRATION.md` - LLM service setup (NEW)

## What's Running?

- **PostgreSQL:** :5432 (data storage)
- **Redis:** :6379 (real-time messaging)
- **FastAPI:** :8000 (API server)
- **Docs:** :8000/docs (interactive API docs)
- **Ollama:** :11434 (LLM inference, optional)
- **LLM Service:** :8600 (event analysis & chat, optional)

## LLM Service (Optional AI Enhancement)

The system now includes an **LLM service** for AI-powered event verification and chat:

```bash
# 1. Start Ollama (if not already running):
ollama serve

# In another terminal, pull the model:
ollama pull deepseek-llm:6.7b

# 2. Start Galaxy with LLM enabled:
docker-compose up -d

# 3. Test the integration:
bash test-llm.sh

# 4. Try the chat assistant:
curl -X POST http://localhost:8600/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is event verification?"}'
```

See **`docs/LLM_QUICKSTART.md`** for quick setup or **`docs/LLM_INTEGRATION.md`** for full documentation.

## Performance

- **Create tenant:** ~100ms
- **Register device:** ~50ms
- **Submit event:** ~50ms (with LLM: ~2-30s depending on inference)
- **Query events:** <100ms
- **WebSocket latency:** <10ms
- **LLM event analysis:** 5-30s (depending on CPU/GPU)

## Next Phase (II)

When ready to scale to multiple planets:
1. Set up libp2p swarm mesh
2. Connect multiple Jetson devices
3. Implement peer discovery (DHT)
4. Add auto-healing relay nodes

## Need Help?

- Check logs: `docker-compose logs -f backend`
- Run tests: `python3 test-phase1.py`
- Read setup guide: `cat PHASE_I_SETUP.md`
- View API docs: `http://localhost:8000/docs`

---

**Remember:** Phase I = Foundation. Phases II-VI = Scale. 🚀
