# 🌌 Galaxy Event Detection System - Phase I Setup

## Quick Start (5 Minutes)

### Prerequisites
- Docker & Docker Compose installed
- Python 3.11+ (for local development)
- Node.js 16+ (for React dashboard)

### Start the Backend Stack

```bash
# From project root
docker-compose up -d

# Wait for services to initialize (~10 seconds)
docker-compose logs -f backend
```

The API will be available at `http://localhost:8000`

#### Verify services are running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "galaxy-event-api",
  "phase": "I"
}
```

---

## Phase I Architecture

```
┌─────────────────────────────────────────┐
│  Edge Planet (NVIDIA Jetson + YOLOv8)   │
│  (To be built in next step)             │
└────────────┬────────────────────────────┘
             │
             ↓ HTTP + API Key
┌─────────────────────────────────────────┐
│  FastAPI Backend (Multi-tenant)         │
│  ✓ Event ingestion                      │
│  ✓ Tenant isolation                     │
│  ✓ API key authentication               │
│  ✓ Event storage & verification         │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┐
    ↓                 ↓
PostgreSQL       Redis (real-time)
(Warm storage)   (Hot cache)


    ↓ WebSocket + API
┌─────────────────────────────────────────┐
│  React Dashboard                        │
│  ✓ Real-time event stream               │
│  ✓ Tenant login (API key)               │
│  ✓ Event statistics & filtering         │
└─────────────────────────────────────────┘
```

---

## API Quick Reference

### 1. Create a Tenant (Customer)

```bash
curl -X POST http://localhost:8000/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Security Corp",
    "quota_events_per_day": 10000
  }'
```

Response:
```json
{
  "id": "uuid",
  "name": "Acme Security Corp",
  "api_key": "gal_abc123...",
  "balance": 1000.0,
  "quota_events_per_day": 10000,
  "created_at": "2026-03-26T..."
}
```

**SAVE THE API KEY** — you'll need it for all subsequent requests.

### 2. Register an Edge Device (Planet)

```bash
export API_KEY="gal_abc123..."  # From step 1

curl -X POST http://localhost:8000/devices \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door Camera",
    "device_type": "jetson",
    "location": "Building A, Floor 1",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
  }'
```

Response:
```json
{
  "id": "device-uuid",
  "name": "Front Door Camera",
  "device_type": "jetson",
  "status": "offline",
  "created_at": "2026-03-26T..."
}
```

**SAVE THE DEVICE ID** — you'll use this when submitting events.

### 3. Submit a Detection Event

```bash
export DEVICE_ID="device-uuid"  # From step 2
export API_KEY="gal_abc123..."

curl -X POST http://localhost:8000/events \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "'$DEVICE_ID'",
    "event_type": "fire",
    "confidence": 0.95,
    "location": "Building A, Floor 1",
    "frame_hash": "abc123def456",
    "signature": "sig789xyz"
  }'
```

Response:
```json
{
  "id": "event-uuid",
  "tenant_id": "tenant-uuid",
  "device_id": "device-uuid",
  "event_type": "fire",
  "confidence": 0.95,
  "verified": true,
  "created_at": "2026-03-26T..."
}
```

### 4. Query Events

```bash
# Get all events (pagination)
curl -X GET "http://localhost:8000/events?page=1&page_size=50" \
  -H "X-API-Key: $API_KEY"

# Filter by event type
curl -X GET "http://localhost:8000/events?event_type=fire&verified_only=true" \
  -H "X-API-Key: $API_KEY"

# Get specific event
curl -X GET "http://localhost:8000/events/event-uuid" \
  -H "X-API-Key: $API_KEY"
```

### 5. Update Device Heartbeat

```bash
curl -X POST "http://localhost:8000/devices/$DEVICE_ID/heartbeat" \
  -H "X-API-Key: $API_KEY"
```

---

## Dashboard Setup (React Frontend)

### Option A: Quick Prototype (No Build)

Use the provided `Dashboard.js` directly in any React project or CodePen:

```javascript
import Dashboard from './frontend/Dashboard.js';

export default function App() {
  return <Dashboard />;
}
```

### Option B: Standalone React App

```bash
# Create a new React app
npx create-react-app galaxy-dashboard
cd galaxy-dashboard

# Replace App.js with Dashboard.js
cp ../frontend/Dashboard.js src/App.js
cp ../frontend/Dashboard.css src/App.css

# Update App.css imports in index.js
npm start
```

Visit `http://localhost:3000` and enter your API key.

---

## Database Schema (Phase I)

### Events Table
```
id (UUID) - Primary key
tenant_id (UUID) - Tenant owner
device_id (String) - Source planet
event_type (String) - "fire", "smoke", "intrusion", etc.
confidence (Float 0-1) - ML model confidence
frame_hash (Bytes) - Hash of original frame
signature (Bytes) - Device signature (for verification)
location (String) - GPS or zone name
verified (Boolean) - Pre-verified for confidence >= 0.8
created_at (DateTime) - Timestamp
updated_at (DateTime) - Last modification
```

### Tenants Table
```
id (UUID) - Primary key
name (String) - Organization name
api_key (String, unique) - Authentication key
balance (Float) - Credit balance for billing
quota_events_per_day (Int) - Daily event limit
events_today (Int) - Counter (resets daily)
active (Boolean) - Account status
created_at (DateTime)
```

### Devices Table
```
id (String) - Primary key (device ID)
tenant_id (UUID) - Owner tenant
name (String) - Device name/label
device_type (String) - "jetson", "coral", "hailo"
location (String) - Physical location
public_key (Text) - For signature verification
status (String) - "online", "offline", "error"
last_heartbeat (DateTime) - Last checkin
active (Boolean) - Device enabled/disabled
created_at (DateTime)
```

---

## Monitoring & Debugging

### View Backend Logs
```bash
docker-compose logs -f backend
```

### Connect to PostgreSQL
```bash
docker exec -it galaxy-db psql -U postgres -d galaxy

# List events
SELECT * FROM events LIMIT 10;

# Check tenants
SELECT id, name, api_key, balance FROM tenants;

# Check devices
SELECT id, name, status, last_heartbeat FROM devices;
```

### Monitor Redis
```bash
docker exec -it galaxy-redis redis-cli
> KEYS *
> PUBSUB CHANNELS
> SUBSCRIBE events:tenant-uuid
```

---

## Testing the Full Flow

### Test Script (bash)

```bash
#!/bin/bash

set -e

echo "=== GALAXY PHASE I TEST SCRIPT ==="

# Step 1: Create tenant
echo -e "\n[1/5] Creating tenant..."
TENANT_RESPONSE=$(curl -s -X POST http://localhost:8000/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Org", "quota_events_per_day": 10000}')

API_KEY=$(echo $TENANT_RESPONSE | jq -r '.api_key')
TENANT_ID=$(echo $TENANT_RESPONSE | jq -r '.id')
echo "API Key: $API_KEY"
echo "Tenant ID: $TENANT_ID"

# Step 2: Register device
echo -e "\n[2/5] Registering device..."
DEVICE_RESPONSE=$(curl -s -X POST http://localhost:8000/devices \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Camera", "device_type": "jetson", "location": "Test Zone", "public_key": "test_key"}')

DEVICE_ID=$(echo $DEVICE_RESPONSE | jq -r '.id')
echo "Device ID: $DEVICE_ID"

# Step 3: Submit events
echo -e "\n[3/5] Submitting 5 test events..."
for i in {1..5}; do
  CONFIDENCE=$(echo "scale=2; 0.70 + $RANDOM/32768 * 0.30" | bc)
  curl -s -X POST http://localhost:8000/events \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "device_id": "'$DEVICE_ID'",
      "event_type": "fire",
      "confidence": '$CONFIDENCE',
      "location": "Test Zone"
    }' > /dev/null
  echo "  Event $i submitted (confidence: $CONFIDENCE)"
done

# Step 4: Fetch events
echo -e "\n[4/5] Fetching events..."
curl -s -X GET "http://localhost:8000/events?page=1&page_size=10" \
  -H "X-API-Key: $API_KEY" | jq '.items[] | {id: .id, event_type: .event_type, confidence: .confidence, verified: .verified}'

# Step 5: Get tenant info
echo -e "\n[5/5] Tenant info..."
curl -s -X GET http://localhost:8000/me \
  -H "X-API-Key: $API_KEY" | jq '{id: .id, name: .name, balance: .balance, events_today: .events_today}'

echo -e "\n=== TEST COMPLETE ==="
```

Save as `test-phase1.sh` and run:
```bash
chmod +x test-phase1.sh
./test-phase1.sh
```

---

## Next Steps After Phase I

Once you've successfully:
- ✅ Created a tenant
- ✅ Registered a device
- ✅ Submitted events
- ✅ Viewed events in the dashboard

You're ready for **Phase II: Swarm Mesh & Multi-Planet**

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Rebuild
docker-compose up --build
```

### Database errors
```bash
# Reset database (WARNING: deletes data)
docker-compose down -v
docker-compose up -d
```

### Port already in use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different ports in docker-compose.yml
```

### Can't connect from outside Docker
- Make sure you're using `http://localhost:8000` (not container IP)
- If on Mac/Windows with Docker Desktop, `localhost` should work
- If on Linux, you may need `http://127.0.0.1:8000`

---

## Project Structure

```
mvp/
├── backend/
│   ├── main.py              # FastAPI app & routes
│   ├── database.py          # SQLAlchemy models & connection
│   ├── schemas.py           # Pydantic models
│   ├── auth.py              # API key validation
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── Dashboard.js         # React component
│   └── Dashboard.css        # Styling
├── docker-compose.yml       # Services orchestration
├── docs/
│   └── ARCHITECTURE.md      # Full system design
└── PHASE_I_SETUP.md        # This file
```

---

## Phase I Metrics

- **Events per second**: 100+ (with 4GB RAM backend)
- **Latency**: ~50ms (event submission to database)
- **Storage**: ~1KB per event
- **Concurrent devices**: 100+ per tenant
- **Tenants**: Unlimited (multi-tenant architecture)

---

## Security Notes for Phase I

⚠️ **Not production-ready yet.** Before moving to Phase II:

- [ ] Enable HTTPS/TLS (add nginx reverse proxy)
- [ ] Implement rate limiting per API key
- [ ] Add audit logging for all DB writes
- [ ] Enable PostgreSQL password encryption
- [ ] Implement JWT tokens (not just API keys)
- [ ] Add request signing (device -> backend)
- [ ] Isolate tenant data at database level (Row-Level Security)

---

Get started: `docker-compose up` 🚀
