import hashlib
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any, Optional

import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

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


class EventsSubmitRequest(BaseModel):
    device_id: str
    event_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


SWARM_INGEST_URL = os.getenv("SWARM_INGEST_URL", "https://swarm-node-1:8443/ingest")
DEFAULT_API_KEY = os.getenv("EDGE_TENANT_API_KEY") or "edge-planet-local"
DEFAULT_DEVICE_ID = os.getenv("EDGE_DEVICE_ID", "")
DEFAULT_LOCATION = os.getenv("EDGE_DEFAULT_LOCATION", "Sector-A")
VERIFY_CERT = os.getenv("EDGE_CA_CERT", "/certs/ca.crt")
CLIENT_CERT = os.getenv("EDGE_CLIENT_CERT", "/certs/edge-planet.crt")
CLIENT_KEY = os.getenv("EDGE_CLIENT_KEY", "/certs/edge-planet.key")
REQ_TIMEOUT = float(os.getenv("EDGE_REQUEST_TIMEOUT", "5"))

FL_ENABLED = os.getenv("FL_ENABLED", "false").lower() == "true"
FL_AGGREGATOR_URL = os.getenv("FL_AGGREGATOR_URL", "http://fl-aggregator:8200")
FL_CLIENT_ID = os.getenv("FL_CLIENT_ID", "edge-planet-1")
FL_TOKEN = os.getenv("FL_AUTH_TOKEN", "")
FL_MODEL_DIM = int(os.getenv("FL_MODEL_DIM", "32"))
FL_SYNC_INTERVAL_SECONDS = int(os.getenv("FL_SYNC_INTERVAL_SECONDS", "120"))

EVENT_TYPES = ["fire", "smoke", "intrusion", "motion", "fall_detection"]

_stream_stop = Event()
_stream_thread: Optional[Thread] = None
_fl_stop = Event()
_fl_thread: Optional[Thread] = None
_fl_lock = Lock()
_fl_weights = np.zeros(FL_MODEL_DIM, dtype=np.float32)
_fl_version = 1

# Prometheus metrics
events_sent_counter = Counter('edge_planet_events_sent_total', 'Total events sent to swarm')
events_failed_counter = Counter('edge_planet_events_failed_total', 'Total events failed to send')
fl_model_version_gauge = Gauge('edge_planet_fl_model_version', 'Current FL model version')


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
        events_failed_counter.inc()
        raise HTTPException(status_code=502, detail=f"swarm unreachable: {exc}") from exc

    if response.status_code >= 300:
        detail = response.text[:500]
        events_failed_counter.inc()
        raise HTTPException(status_code=502, detail=f"swarm rejected event: {detail}")

    data = response.json()
    events_sent_counter.inc()
    logger.info("event published envelope_id=%s event_type=%s", data.get("envelope_id"), event.event_type)
    return data


def _mock_local_training(base_weights: np.ndarray) -> tuple[np.ndarray, int]:
    # Simulate local training noise without sending raw image data to the aggregator.
    grad = np.random.normal(loc=0.0, scale=0.01, size=base_weights.shape).astype(np.float32)
    updated = base_weights + grad
    sample_count = random.randint(64, 256)
    return updated, sample_count


def _fetch_global_model() -> None:
    global _fl_weights, _fl_version

    try:
        resp = requests.get(f"{FL_AGGREGATOR_URL}/fl/model/latest", timeout=REQ_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("FL model fetch failed status=%s", resp.status_code)
            return

        data = resp.json()
        weights = np.array(data.get("weights", []), dtype=np.float32)
        if len(weights) != len(_fl_weights):
            logger.warning("FL model dimension mismatch got=%d expected=%d", len(weights), len(_fl_weights))
            return

        with _fl_lock:
            _fl_weights = weights
            _fl_version = int(data.get("version", _fl_version))
    except requests.RequestException as exc:
        logger.error("FL global model fetch failed: %s", exc)


def _push_local_update(weights: np.ndarray, sample_count: int) -> None:
    payload = {
        "client_id": FL_CLIENT_ID,
        "weights": weights.tolist(),
        "sample_count": sample_count,
    }
    if FL_TOKEN:
        payload["token"] = FL_TOKEN

    try:
        resp = requests.post(
            f"{FL_AGGREGATOR_URL}/fl/model/update",
            json=payload,
            timeout=REQ_TIMEOUT,
        )
        if resp.status_code >= 300:
            logger.warning("FL update rejected status=%s body=%s", resp.status_code, resp.text[:200])
            return

        body = resp.json()
        logger.info(
            "FL update accepted client=%s current_version=%s",
            FL_CLIENT_ID,
            body.get("current_version"),
        )
    except requests.RequestException as exc:
        logger.error("FL update push failed: %s", exc)


def _fl_loop() -> None:
    logger.info("FL loop started enabled=%s interval=%ss", FL_ENABLED, FL_SYNC_INTERVAL_SECONDS)

    _fetch_global_model()

    while not _fl_stop.is_set():
        with _fl_lock:
            local_base = _fl_weights.copy()

        local_weights, sample_count = _mock_local_training(local_base)
        _push_local_update(local_weights, sample_count)
        _fetch_global_model()
        _fl_stop.wait(FL_SYNC_INTERVAL_SECONDS)

    logger.info("FL loop stopped")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "edge-planet-simulator",
        "swarm_ingest_url": SWARM_INGEST_URL,
        "fl_enabled": FL_ENABLED,
        "fl_model_version": _fl_version,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.on_event("startup")
def startup() -> None:
    global _fl_thread
    if FL_ENABLED and (not _fl_thread or not _fl_thread.is_alive()):
        _fl_stop.clear()
        _fl_thread = Thread(target=_fl_loop, daemon=True)
        _fl_thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _fl_stop.set()


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


@app.post("/events")
def submit_event(request: EventsSubmitRequest) -> dict:
    # Compatibility endpoint retained for Phase V test flow and legacy clients.
    api_key = DEFAULT_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="EDGE_TENANT_API_KEY is required")

    location = request.metadata.get("location") if request.metadata else None
    event = EventPayload(
        device_id=request.device_id,
        event_type=request.event_type,
        confidence=request.confidence,
        location=location or DEFAULT_LOCATION,
        frame_hash=random_hex(64),
        signature=random_hex(64),
    )
    result = send_to_swarm(api_key, event)
    envelope_id = result.get("envelope_id", "")
    return {
        "status": "accepted",
        "id": envelope_id,
        "event_id": envelope_id,
        "envelope_id": envelope_id,
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
        "fl_enabled": FL_ENABLED,
        "fl_aggregator_url": FL_AGGREGATOR_URL,
        "fl_client_id": FL_CLIENT_ID,
        "fl_sync_interval_seconds": FL_SYNC_INTERVAL_SECONDS,
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


@app.get("/fl/status")
def fl_status() -> dict:
    return {
        "enabled": FL_ENABLED,
        "client_id": FL_CLIENT_ID,
        "model_version": _fl_version,
        "model_dim": len(_fl_weights),
        "thread_running": bool(_fl_thread and _fl_thread.is_alive()),
    }


@app.post("/fl/train-once")
def fl_train_once() -> dict:
    if not FL_ENABLED:
        raise HTTPException(status_code=409, detail="federated learning is disabled")

    with _fl_lock:
        base = _fl_weights.copy()

    local_weights, sample_count = _mock_local_training(base)
    _push_local_update(local_weights, sample_count)
    _fetch_global_model()

    return {
        "status": "ok",
        "sample_count": sample_count,
        "model_version": _fl_version,
    }


@app.get("/metrics")
def metrics():
    fl_model_version_gauge.set(_fl_version)
    return generate_latest()
