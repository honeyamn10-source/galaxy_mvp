import hashlib
import hmac
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import requests
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from xgboost import XGBClassifier
from prometheus_client import Counter, Gauge, generate_latest

from shared.auth_middleware import (
    configure_cors,
    prometheus_response,
    require_request_context,
    required_secret,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("predictive-service")

app = FastAPI(
    title="Galaxy Predictive Analytics",
    version="0.4.0",
    description="Phase IV predictive analytics service that produces risk alerts and publishes them into the swarm.",
)

configure_cors(app)

AUTHORITY_URL = os.getenv("PRED_AUTHORITY_URL", "http://authority-chain:1317")
SWARM_PRED_URL = os.getenv("PRED_SWARM_PUBLISH_URL", "https://swarm-node-1:8443/ingest-prediction")
SWARM_TOKEN = os.getenv("PRED_SWARM_API_KEY", "").strip()
CA_CERT = os.getenv("PRED_CA_CERT", "/certs/ca.crt")
CLIENT_CERT = os.getenv("PRED_CLIENT_CERT", "/certs/edge-planet.crt")
CLIENT_KEY = os.getenv("PRED_CLIENT_KEY", "/certs/edge-planet.key")
REQUEST_TIMEOUT = float(os.getenv("PRED_REQUEST_TIMEOUT", "8"))
LOOP_INTERVAL_SECONDS = int(os.getenv("PRED_LOOP_INTERVAL_SECONDS", "60"))
TRAIN_WINDOW = int(os.getenv("PRED_TRAIN_WINDOW", "200"))
RISK_THRESHOLD = float(os.getenv("PRED_RISK_THRESHOLD", "0.65"))
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_BASE_URL = os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5/weather")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

_loop_stop = threading.Event()
_loop_thread: threading.Thread | None = None

model = XGBClassifier(
    n_estimators=40,
    max_depth=4,
    learning_rate=0.1,
    objective="binary:logistic",
    eval_metric="logloss",
)
model_ready = False
latest_predictions: list[dict[str, Any]] = []

# Prometheus metrics
predictions_generated_counter = Counter('predictive_service_predictions_generated_total', 'Total predictions generated')
model_trains_counter = Counter('predictive_service_model_trains_total', 'Total model training runs')
model_ready_gauge = Gauge('predictive_service_model_ready', 'Whether prediction model is ready (1=ready, 0=not ready)')


class PredictionStatus(BaseModel):
    status: str
    model_ready: bool
    prediction_count: int
    loop_interval_seconds: int


def _extract_features(event: dict[str, Any], weather: dict[str, Any]) -> list[float]:
    confidence = float(event.get("event", {}).get("confidence", 0.5))
    event_type = event.get("event", {}).get("event_type", "unknown")
    event_score = int(hashlib.sha256(str(event_type).encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    temp_c = float(weather.get("main", {}).get("temp", 295.0)) - 273.15
    humidity = float(weather.get("main", {}).get("humidity", 50.0)) / 100.0
    hour = datetime.now(timezone.utc).hour / 23.0

    return [confidence, event_score, temp_c / 50.0, humidity, hour]


def _fetch_weather(location_hint: str) -> dict[str, Any]:
    if not WEATHER_API_KEY:
        return {"main": {"temp": 296.0, "humidity": 55.0}}

    city = location_hint or "London"
    try:
        resp = requests.get(
            WEATHER_BASE_URL,
            params={"q": city, "appid": WEATHER_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass

    return {"main": {"temp": 296.0, "humidity": 55.0}}


def _fetch_events() -> list[dict[str, Any]]:
    try:
        resp = requests.get(
            f"{AUTHORITY_URL}/galaxy/v1/events",
            params={"limit": TRAIN_WINDOW},
            headers={"X-Internal-Auth": INTERNAL_API_KEY} if INTERNAL_API_KEY else None,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("events", [])
    except requests.RequestException as exc:
        logger.error("failed to fetch authority events: %s", exc)
    return []


def _fit_model(events: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    features = []
    labels = []

    for event in events:
        location = event.get("event", {}).get("location", "")
        weather = _fetch_weather(location)
        feat = _extract_features(event, weather)
        features.append(feat)

        status = event.get("status", "pending")
        labels.append(1 if status == "verified" else 0)

    if len(features) < 4:
        return np.empty((0, 5)), np.empty((0,))

    x = np.array(features, dtype=np.float32)
    y = np.array(labels, dtype=np.int32)
    return x, y


def _prediction_signature(pred: dict[str, Any]) -> str:
    canonical = "\n".join(
        [
            str(pred.get("device_id", "")),
            str(pred.get("event_type", "")),
            f"{float(pred.get('confidence', 0.0)):.6f}",
            str(pred.get("location", "")),
            str(pred.get("frame_hash", "")),
        ]
    )
    return hmac.new(
        SWARM_TOKEN.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _publish_prediction(pred: dict[str, Any]) -> None:
    pred["signature"] = _prediction_signature(pred)
    payload = {
        "api_key": SWARM_TOKEN,
        "prediction": pred,
    }
    try:
        resp = requests.post(
            SWARM_PRED_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            verify=CA_CERT,
            cert=(CLIENT_CERT, CLIENT_KEY),
        )
        if resp.status_code >= 300:
            logger.warning("prediction publish rejected status=%s body=%s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.error("prediction publish failed: %s", exc)


def _make_prediction_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    predictions = []
    if not events:
        return predictions

    zones = {}
    for event in events:
        zone = event.get("event", {}).get("location", "unknown-zone")
        zones.setdefault(zone, []).append(event)

    for zone, zone_events in zones.items():
        last = zone_events[0]
        weather = _fetch_weather(zone)
        feat = np.array([_extract_features(last, weather)], dtype=np.float32)

        if model_ready:
            risk = float(model.predict_proba(feat)[0][1])
        else:
            risk = float(last.get("event", {}).get("confidence", 0.5))

        risk_level = "high" if risk >= RISK_THRESHOLD else "normal"
        seed = f"{zone}|{risk:.4f}|{datetime.now(timezone.utc).isoformat()}"

        predictions.append(
            {
                "device_id": "predictive-service",
                "event_type": "prediction_alert",
                "confidence": max(min(risk, 0.999), 0.0),
                "location": zone,
                "frame_hash": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
                "signature": "",
                "risk_level": risk_level,
                "meta": {
                    "zone_event_count": len(zone_events),
                    "forecast_horizon": "1h",
                    "weather_temp_k": weather.get("main", {}).get("temp"),
                    "weather_humidity": weather.get("main", {}).get("humidity"),
                },
            }
        )

    return predictions


def _loop() -> None:
    global model_ready, latest_predictions

    logger.info("predictive loop started interval=%ds", LOOP_INTERVAL_SECONDS)
    while not _loop_stop.is_set():
        events = _fetch_events()
        x, y = _fit_model(events)

        if len(x) >= 4 and len(set(y.tolist())) > 1:
            model_trains_counter.inc()
            try:
                model.fit(x, y)
                model_ready = True
            except Exception as exc:
                logger.error("model fit failed: %s", exc)

        latest_predictions = _make_prediction_events(events)
        for pred in latest_predictions:
            _publish_prediction(pred)

        predictions_generated_counter.add(len(latest_predictions))
        logger.info("generated predictions=%d model_ready=%s", len(latest_predictions), model_ready)
        _loop_stop.wait(LOOP_INTERVAL_SECONDS)

    logger.info("predictive loop stopped")


@app.on_event("startup")
def startup() -> None:
    global _loop_thread
    required_secret("INTERNAL_API_KEY")
    required_secret("PRED_SWARM_API_KEY", minimum_length=24)
    if _loop_thread and _loop_thread.is_alive():
        return
    _loop_stop.clear()
    _loop_thread = threading.Thread(target=_loop, daemon=True)
    _loop_thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _loop_stop.set()


@app.get("/health", response_model=PredictionStatus)
def health() -> PredictionStatus:
    return PredictionStatus(
        status="ok",
        model_ready=model_ready,
        prediction_count=len(latest_predictions),
        loop_interval_seconds=LOOP_INTERVAL_SECONDS,
    )


@app.get("/predictions/latest")
def predictions_latest(_: dict = Depends(require_request_context)) -> dict[str, Any]:
    return {
        "items": latest_predictions,
        "count": len(latest_predictions),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/predictions/run-once")
def run_once(_: dict = Depends(require_request_context)) -> dict[str, Any]:
    events = _fetch_events()
    x, y = _fit_model(events)

    global model_ready, latest_predictions
    if len(x) >= 4 and len(set(y.tolist())) > 1:
        model_trains_counter.inc()
        try:
            model.fit(x, y)
            model_ready = True
        except Exception as exc:
            logger.error("model fit failed: %s", exc)

    latest_predictions = _make_prediction_events(events)
    for pred in latest_predictions:
        _publish_prediction(pred)

    predictions_generated_counter.add(len(latest_predictions))
    return {
        "status": "ok",
        "generated": len(latest_predictions),
        "model_ready": model_ready,
    }


@app.get("/metrics")
def metrics():
    model_ready_gauge.set(1 if model_ready else 0)
    return prometheus_response(generate_latest())
