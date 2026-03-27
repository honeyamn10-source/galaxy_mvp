import hashlib
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("edge-planet")

app = FastAPI(
    title="Edge Planet Simulator",
    version="2.0.0",
    description="Phase II edge simulator that sends detections into the P2P swarm ingress.",
)


class EventPayload(BaseModel):
    device_id: str
    event_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    location: Optional[str] = None
    frame_hash: Optional[str] = None
    signature: Optional[str] = None


class EmitRequest(BaseModel):
    api_key: Optional[str] = None
    device_id: Optional[str] = None
    event_type: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    location: Optional[str] = None


class EmitBatchRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=1000)
    api_key: Optional[str] = None
    device_id: Optional[str] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    interval_ms: int = Field(default=100, ge=0, le=60000)


class StreamRequest(BaseModel):
    count: int = Field(default=50, ge=1, le=100000)
    interval_ms: int = Field(default=250, ge=10, le=60000)
    api_key: Optional[str] = None
    device_id: Optional[str] = None


SWARM_INGEST_URL = os.getenv("SWARM_INGEST_URL", "https://swarm-node-1:8443/ingest")
DEFAULT_API_KEY = os.getenv("EDGE_TENANT_API_KEY", "")
DEFAULT_DEVICE_ID = os.getenv("EDGE_DEVICE_ID", "")
DEFAULT_LOCATION = os.getenv("EDGE_DEFAULT_LOCATION", "Sector-A")
VERIFY_CERT = os.getenv("EDGE_CA_CERT", "/certs/ca.crt")
CLIENT_CERT = os.getenv("EDGE_CLIENT_CERT", "/certs/edge-planet.crt")
CLIENT_KEY = os.getenv("EDGE_CLIENT_KEY", "/certs/edge-planet.key")
REQ_TIMEOUT = float(os.getenv("EDGE_REQUEST_TIMEOUT", "5"))

EVENT_TYPES = ["fire", "smoke", "intrusion", "motion", "fall_detection"]

_stream_stop = Event()
_stream_thread: Optional[Thread] = None


def random_hex(size: int) -> str:
    return hashlib.sha256(f"{time.time_ns()}:{random.random()}".encode("utf-8")).hexdigest()[:size]


def build_event(device_id: str, event_type: Optional[str], confidence: Optional[float], location: Optional[str]) -> EventPayload:
    evt_type = event_type or random.choice(EVENT_TYPES)
    conf = confidence if confidence is not None else round(random.uniform(0.65, 0.99), 2)
    loc = location or DEFAULT_LOCATION
    frame_hash = random_hex(64)
    signature = random_hex(64)

    return EventPayload(
        device_id=device_id,
        event_type=evt_type,
        confidence=conf,
        location=loc,
        frame_hash=frame_hash,
        signature=signature,
    )


def send_to_swarm(api_key: str, event: EventPayload) -> dict:
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    payload = {"api_key": api_key, "event": event.model_dump()}

    try:
        response = requests.post(
            SWARM_INGEST_URL,
            json=payload,
            timeout=REQ_TIMEOUT,
            verify=VERIFY_CERT,
            cert=(CLIENT_CERT, CLIENT_KEY),
        )
    except requests.RequestException as exc:
        logger.error("failed to publish to swarm: %s", exc)
        raise HTTPException(status_code=502, detail=f"swarm unreachable: {exc}") from exc

    if response.status_code >= 300:
        detail = response.text[:500]
        raise HTTPException(status_code=502, detail=f"swarm rejected event: {detail}")

    data = response.json()
    logger.info("event published envelope_id=%s event_type=%s", data.get("envelope_id"), event.event_type)
    return data


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "edge-planet-simulator",
        "swarm_ingest_url": SWARM_INGEST_URL,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/emit")
def emit_once(request: EmitRequest) -> dict:
    api_key = request.api_key or DEFAULT_API_KEY
    device_id = request.device_id or DEFAULT_DEVICE_ID
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    event = build_event(device_id, request.event_type, request.confidence, request.location)
    result = send_to_swarm(api_key, event)
    return {
        "status": "published",
        "event": event.model_dump(),
        "swarm": result,
    }


@app.post("/emit-batch")
def emit_batch(request: EmitBatchRequest) -> dict:
    api_key = request.api_key or DEFAULT_API_KEY
    device_id = request.device_id or DEFAULT_DEVICE_ID
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    accepted = []
    for _ in range(request.count):
        event = build_event(device_id, request.event_type, None, request.location)
        result = send_to_swarm(api_key, event)
        accepted.append({"event_type": event.event_type, "envelope_id": result.get("envelope_id")})
        if request.interval_ms > 0:
            time.sleep(request.interval_ms / 1000)

    return {
        "status": "published",
        "count": request.count,
        "results": accepted,
    }


@app.post("/stream/start")
def start_stream(request: StreamRequest) -> dict:
    global _stream_thread

    if _stream_thread and _stream_thread.is_alive():
        raise HTTPException(status_code=409, detail="stream already running")

    api_key = request.api_key or DEFAULT_API_KEY
    device_id = request.device_id or DEFAULT_DEVICE_ID
    if not api_key or not device_id:
        raise HTTPException(status_code=400, detail="api_key and device_id are required")

    _stream_stop.clear()

    def worker() -> None:
        logger.info("starting stream count=%d interval_ms=%d", request.count, request.interval_ms)
        sent = 0
        while sent < request.count and not _stream_stop.is_set():
            event = build_event(device_id, None, None, DEFAULT_LOCATION)
            try:
                send_to_swarm(api_key, event)
            except Exception as exc:
                logger.error("stream publish failed at event=%d: %s", sent + 1, exc)
            sent += 1
            time.sleep(request.interval_ms / 1000)
        logger.info("stream completed sent=%d", sent)

    _stream_thread = Thread(target=worker, daemon=True)
    _stream_thread.start()

    return {
        "status": "started",
        "count": request.count,
        "interval_ms": request.interval_ms,
    }


@app.post("/stream/stop")
def stop_stream() -> dict:
    _stream_stop.set()
    return {"status": "stopping"}


@app.get("/config")
def current_config() -> dict:
    return {
        "swarm_ingest_url": SWARM_INGEST_URL,
        "default_device_id": DEFAULT_DEVICE_ID,
        "default_location": DEFAULT_LOCATION,
        "client_cert": CLIENT_CERT,
        "ca_cert": VERIFY_CERT,
    }


@app.post("/debug/payload")
def debug_payload(request: EmitRequest) -> dict:
    api_key = request.api_key or DEFAULT_API_KEY
    device_id = request.device_id or DEFAULT_DEVICE_ID
    event = build_event(device_id or "missing-device", request.event_type, request.confidence, request.location)
    return {
        "api_key_present": bool(api_key),
        "payload": {
            "api_key": "***" if api_key else "",
            "event": json.loads(event.model_dump_json()),
        },
    }
