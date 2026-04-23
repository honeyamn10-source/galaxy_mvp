# 🚀 Galaxy MVP - Live Camera Testing Quick Start

**Status:** All services operational, dashboard live, ready for camera integration  
**Time to live camera:** 5-10 minutes  

---

## 🎯 The Goal
See your laptop camera (or any RTSP source) in the Galaxy MVP security dashboard with real-time threat detection, LLM analysis, and event tracking.

---

## ⚡ 60-Second Quick Start

### 1. Start Camera Stream (Pick ONE option)

**Option A: USB Webcam (Simplest)**
```bash
# Install ffmpeg (one-time)
sudo dnf install ffmpeg

# Run this to stream your webcam
ffmpeg -f v4l2 -input_format mjpeg -i /dev/video0 \
  -c:v libx264 -preset ultrafast -f rtsp rtsp://localhost:8554/camera
```
Keep this terminal running!

**Option B: Mock RTSP Server (for testing without camera)**
```bash
docker run -d -p 8554:8554 bluenviron/mediamtx:latest
```

### 2. Enable Camera in Galaxy MVP (Another Terminal)
```bash
cd /home/honey/Documents/github/mvp
export RTSP_URL="rtsp://localhost:8554/camera"
docker compose up -d edge-planet
```

### 3. Watch Camera Loop Start
```bash
docker logs galaxy-edge-planet --follow
```

Look for: **✅ "Camera loop started"**

### 4. Open Dashboard (Browser)
```
http://localhost:8000
```

Login:
- Email: `admin@test.com`
- Password: `Test1234!`

---

## 📊 What You'll See in Dashboard

```
┌──────────────────────────────────────────────────┐
│  Galaxy MVP Security Dashboard                   │
├──────────────────────────────────────────────────┤
│                                                  │
│  📊 Stats                                        │
│  ┌─────────┬──────────┬─────────┬──────────┐    │
│  │ Total   │ Verified │ Pending │ High Risk│    │
│  │   7     │    5     │    2    │    1     │    │
│  └─────────┴──────────┴─────────┴──────────┘    │
│                                                  │
│  📜 Recent Events                                │
│  ┌──────────────────────────────────────────┐  │
│  │ 🔫 gun_detection     | Confidence: 94%   │  │
│  │    LLM: "Firearm detected with high..."  │  │
│  │    Device: planet-laptop     [verified]  │  │
│  │                                          │  │
│  │ 🚗 vehicle_detection | Confidence: 87%   │  │
│  │    LLM: "Vehicle motion detected..."     │  │
│  │    Device: planet-laptop     [pending]   │  │
│  │                                          │  │
│  │ 👥 person_detection  | Confidence: 91%  │  │
│  │    LLM: "Person detected in frame..."    │  │
│  │    Device: planet-laptop     [verified]  │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  💬 Chat Widget (Ask Galaxy MVP questions!)     │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 🔄 Live Testing Workflow

### Test 1: Motion Detection
1. Move in front of camera
2. Wait 1-2 seconds
3. Check dashboard for **person_detection** or **motion** event
4. See LLM analysis: "Person detected in frame..."

### Test 2: Object Detection
1. Hold up object (phone, keys, etc.)
2. Watch for **intrusion_detection** or **vehicle_detection**
3. Event should appear with LLM verdict

### Test 3: Threat Detection (If available)
1. Show firearm-shaped object near camera
2. Watch for **gun_detection** or **weapon_detection** event
3. Confidence score should be high
4. LLM should flag as security threat

### Test 4: Rate Limiting
1. Rapidly click "Refresh Events" or reload page many times
2. After 10 rapid attempts, you should see **429 Too Many Requests**
3. This protects against abuse!

---

## 🔍 Monitoring

### Watch Real-Time Logs
```bash
# In separate terminals:

# Terminal 1: Camera feed processing
docker logs galaxy-edge-planet --follow

# Terminal 2: LLM analysis  
docker logs galaxy-llm-service --follow

# Terminal 3: Event verification
docker logs galaxy-authority-chain --follow

# Terminal 4: Compliance enforcement
docker logs galaxy-compliance-engine --follow
```

### Check Event in Database
```bash
# Connect to database and query events
docker exec -it galaxy-db psql -U galaxy -d galaxy -c \
  "SELECT device_id, event_type, confidence, llm_reason, created_at FROM events ORDER BY created_at DESC LIMIT 5;"
```

---

## 🎛 Tuning Camera Parameters

Edit these in `docker-compose.override.yml`:

```yaml
edge-planet:
  environment:
    RTSP_URL: "rtsp://localhost:8554/camera"
    CAMERA_POLL_INTERVAL_SECONDS: "1.0"      # How often to capture frames
    CAMERA_MIN_CONFIDENCE: "0.75"             # Confidence threshold
    EDGE_EVENT_TYPES: "fire,smoke,intrusion,motion,fall_detection,weapon_detection,gun_detection,vehicle_detection,person_detection"
```

Then restart:
```bash
docker compose up -d edge-planet
```

---

## 🤖 Using Different LLM Models

Switch to faster or better models:

```bash
# Use smaller model (faster)
export OLLAMA_MODEL="llama3.2:3b"

# Use larger model (better accuracy)
export OLLAMA_MODEL="qwen2.5:7b"

# Restart LLM service
docker compose up -d llm-service
```

Check available models:
```bash
curl http://localhost:11434/api/tags | jq '.models[].name'
```

---

## 🐛 Troubleshooting

### Camera Not Showing Events?
```bash
# Check edge-planet is running
docker ps | grep edge-planet

# Check RTSP URL is accessible
ffprobe rtsp://localhost:8554/camera

# Check logs
docker logs galaxy-edge-planet | grep -i error
```

### Events Not in Dashboard?
```bash
# Check authority-chain is accepting events
docker logs galaxy-authority-chain | grep -i "event\|submit"

# Check compliance engine
docker logs galaxy-compliance-engine | head -50
```

### LLM Not Analyzing?
```bash
# Check LLM service health
curl http://localhost:8600/health

# Check Ollama is running
curl http://localhost:11434/api/tags

# Check logs
docker logs galaxy-llm-service | tail -20
```

### Dashboard Not Updating?
```bash
# Check WebSocket connection
docker logs galaxy-nginx-gateway | grep -i "websocket\|ws"

# Try refreshing browser (Ctrl+Shift+R)
# Check browser console for errors (F12)
```

---

## ✅ Verification Checklist

- [ ] ffmpeg or RTSP server started
- [ ] RTSP_URL environment variable set
- [ ] edge-planet restarted: `docker compose up -d edge-planet`
- [ ] Camera loop started (check logs)
- [ ] Dashboard loads: http://localhost:8000
- [ ] Can log in with admin credentials
- [ ] At least one test event appears in dashboard
- [ ] Events show LLM analysis reason
- [ ] Timestamps are recent (not old)
- [ ] Can see confidence scores for events

---

## 🎯 Success Criteria

When everything works, you should see:

1. **Dashboard loads** at http://localhost:8000
2. **Login works** with admin@test.com
3. **Stats show events** (Total > 0)
4. **Event feed** displays real-time detections
5. **LLM analysis** present for each event
6. **Device name** shown (e.g., "planet-laptop")
7. **Timestamps** are recent
8. **Status** shows "verified" or "pending"

---

## 📚 Additional Resources

- **Full Camera Setup:** See `CAMERA_SETUP_GUIDE.md`
- **Complete Status:** See `STATUS_REPORT.md`
- **Architecture Diagram:** See `ARCHITECTURE_SUMMARY.md`
- **Phase Documentation:** See `PHASE_V_SETUP.md`, `PHASE_VI_SETUP.md`

---

## 🎬 Example Complete Flow

```
Your Laptop Camera
        ↓ (via ffmpeg RTSP)
RTSP Stream (localhost:8554)
        ↓
edge-planet service (8100)
  • Captures frame
  • Runs inference
  • Detects "person" in frame
  • Creates event
        ↓
swarm-node (consensus)
        ↓
authority-chain (1317)
  • Stores event on ledger
  • Signs with ECDSA
        ↓
llm-service (8600)
  • Analyzes: "Person detected in frame, no immediate threat"
  • Confidence: 0.91
  • Status: VERIFIED
        ↓
compliance-engine (8400)
  • Checks security policies
  • Marks as compliant
        ↓
webhook-service (8500)
  • Sends notifications
        ↓
frontend (8000)
  **📊 YOUR BROWSER** 
  • See in event feed: "person_detection, 91%, Verified"
  • See LLM analysis
  • Monitor in real-time
```

---

## 🚀 Next Steps After Setup

1. **Test different event types**
   - Move around for person detection
   - Show objects for intrusion detection
   - Create scenarios for threat detection

2. **Monitor performance**
   - Check latency (should be <2 seconds)
   - Verify LLM inference time
   - Check database performance

3. **Integrate with external systems**
   - Set up webhooks to your server
   - Create alerts for high-risk events
   - Build custom notification rules

4. **Deploy to production**
   - Use docker-compose in swarm mode
   - Set up Kubernetes manifests
   - Configure TLS certificates
   - Enable persistent storage

---

**You're 5 minutes away from live security monitoring! 🎯**

Start with Option A (USB webcam) for fastest setup, then open the dashboard.

Questions? Check the troubleshooting section or review logs.
