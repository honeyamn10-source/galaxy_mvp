# Camera Integration Guide

This guide explains how to attach real RTSP/IP cameras to Galaxy MVP through Edge Planet.

## Overview

Edge Planet supports two camera modes:
- Simulator mode: emits synthetic events.
- RTSP mode: reads frames from a real camera and emits detections.

RTSP mode is enabled when RTSP_URL is configured.

## Environment Variables

Required:
- RTSP_URL: RTSP stream URL from your camera.

Optional:
- REAL_INFERENCE_URL: HTTP endpoint for real inference results.
- CAMERA_POLL_INTERVAL_SECONDS: frame polling interval. Default: 1.5.
- CAMERA_MIN_CONFIDENCE: minimum confidence threshold. Default: 0.75.
- EDGE_DEVICE_ID: override camera device id.

If REAL_INFERENCE_URL is not set, Edge Planet falls back to local synthetic classification for demo continuity.

## Quick Start

export RTSP_URL=rtsp://username:password@camera-ip:554/stream
export EDGE_DEVICE_ID=camera-lobby-01
export REAL_INFERENCE_URL=http://your-inference-service:9000/infer

docker compose up -d edge-planet

## Health And Camera Status

Use these endpoints:
- GET http://localhost:8100/health
- GET http://localhost:8100/camera/status
- POST http://localhost:8100/camera/start
- POST http://localhost:8100/camera/stop

## Inference Service Contract

When REAL_INFERENCE_URL is configured, Edge Planet sends:
- frame_hash
- source
- rtsp

Expected response:
{
  "event_type": "intrusion",
  "confidence": 0.92
}

## Notes

- The container includes opencv-python-headless for RTSP reads.
- Keep camera credentials in environment variables or secrets, not committed files.
- For production, use TLS and private networking between edge-planet and inference services.
