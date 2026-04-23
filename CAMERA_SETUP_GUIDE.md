# Galaxy MVP - Live Camera Setup Guide

## 📹 Current Status
✅ Platform: Fully operational and healthy (all 15 services running)
✅ Threat Detection: Ready (fire, guns, smoke, intrusion, motion, fall detection)  
✅ LLM Analysis: Available (Ollama + OpenRouter with auto-fallback)
✅ Dashboard: Live at http://localhost:8000
✅ Event Pipeline: Working (camera → classification → compliance → webhooks → frontend)

---

## 🎥 Option 1: USB Webcam (Recommended for Testing)

### Linux (using ffmpeg)
```bash
# Install ffmpeg if not present
sudo dnf install ffmpeg

# Stream USB webcam to RTSP server
ffmpeg -f v4l2 -input_format mjpeg -i /dev/video0 \
  -c:v libx264 -preset ultrafast -f rtsp rtsp://localhost:8554/camera
```

### macOS
```bash
# Using built-in camera with ffmpeg
ffmpeg -f avfoundation -i "0" -c:v libx264 -preset ultrafast \
  -f rtsp rtsp://localhost:8554/camera
```

### Windows (WSL2)
```bash
# Enable USB passthrough in WSL2, then use Linux commands above
```

---

## 🌐 Option 2: RTSP Network Camera

If you have an IP camera:
```bash
export RTSP_URL="rtsp://username:password@192.168.1.100/stream"
docker compose up -d edge-planet
```

---

## 🔧 Option 3: Mock RTSP Server with Docker

Start an RTSP server in Docker:
```bash
docker run -d \
  -p 8554:8554 \
  -p 1935:1935 \
  bluenviron/mediamtx:latest
```

Then stream to it:
```bash
ffmpeg -f v4l2 -input_format mjpeg -i /dev/video0 \
  -c:v libx264 -preset ultrafast \
  -f rtsp rtsp://host.docker.internal:8554/camera
```

---

## 🚀 Enable Camera Feed in Galaxy MVP

### 1. Set RTSP URL
```bash
cd /home/honey/Documents/github/mvp

# Option A: Direct export
export RTSP_URL="rtsp://localhost:8554/camera"

# Option B: Update .env file
echo "RTSP_URL=rtsp://localhost:8554/camera" >> .env
```

### 2. Restart edge-planet service
```bash
docker compose up -d --build edge-planet
```

### 3. Check camera loop in logs
```bash
docker logs galaxy-edge-planet --follow
```

Look for:
- ✅ "Camera loop started"
- ✅ "Frame captured" messages
- ⚠️ "RTSP connection unavailable" (will retry gracefully)

---

## 🎯 Test Threat Detection

The platform detects:
- 🔥 **Fire** - flame/heat signature
- 🔫 **Guns/Weapons** - firearm shapes
- 💨 **Smoke** - gray/white clouds
- 👥 **Intrusion** - unauthorized persons
- 🚗 **Vehicle Detection** - cars/trucks
- 🧑 **Person Detection** - human figures
- ⚠️ **Fall Detection** - person on ground

---

## 📊 Live Monitoring

1. Open Dashboard: http://localhost:8000
2. Go to "Events" or "Security" section
3. Watch real-time threat detections appear as they're classified by LLM
4. See confidence scores and LLM analysis verdicts

---

## 🐛 Troubleshooting

### Camera not connecting?
```bash
# Check edge-planet logs
docker logs galaxy-edge-planet

# Verify RTSP URL is accessible
ffprobe rtsp://localhost:8554/camera  # Install with: sudo dnf install ffmpeg

# Check edge-planet environment
docker exec galaxy-edge-planet env | grep RTSP
```

### No events appearing?
```bash
# Check LLM service
docker logs galaxy-llm-service

# Verify authority-chain
docker logs galaxy-authority-chain | grep -i event

# Check compliance engine
docker logs galaxy-compliance-engine
```

### Slow inference?
- Reduce CAMERA_POLL_INTERVAL_SECONDS in docker-compose.override.yml
- Ensure Ollama is running: `curl http://localhost:11434/api/tags`
- Check available models: `ollama list`

---

## 🔒 Security Notes

- Camera feeds are encrypted via mTLS between edge-planet and swarm-node
- Events are signed with digital signatures
- LLM analysis is stored with compliance metadata
- All webhook deliveries include HMAC signatures

---

## 📝 Advanced: Custom Models

To use different Ollama models:
```bash
export LLM_PROVIDER="ollama"
export OLLAMA_MODEL="qwen2.5:7b"  # or any other installed model
docker compose up -d llm-service
```

Available local models (run `ollama list`):
- llama3.2:3b (fastest)
- tinyllama (very fast)
- qwen2.5:7b (good balance)
- nomic-embed-text (embeddings)

---

## ✅ Validation Checklist

After setup, verify:
- [ ] Dashboard loads at http://localhost:8000
- [ ] Can log in with admin or created account
- [ ] Camera loop is running (check logs)
- [ ] At least one test event was submitted and appears in dashboard
- [ ] Events show LLM analysis reason
- [ ] Rate limiting works (try rapid requests)

---

## 🎬 Complete Flow

```
USB Webcam
    ↓
ffmpeg RTSP stream
    ↓
edge-planet (inference + threat detection)
    ↓
swarm-node (consensus)
    ↓
authority-chain (event ledger)
    ↓
llm-service (event analysis)
    ↓
compliance-engine (policy verification)
    ↓
webhook-service (notifications)
    ↓
frontend (dashboard + websocket updates)
    ↓
**Live Security Dashboard** 🎯
```

---

**Status:** Ready for live camera integration  
**Dashboard:** http://localhost:8000  
**Last verified:** All services healthy ✅
