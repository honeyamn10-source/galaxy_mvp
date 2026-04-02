import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

import psycopg2
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("webhook-service")

app = FastAPI(
    title="Galaxy Webhook Delivery",
    version="0.5.0",
    description="Phase V tenant webhook delivery with retries and dead-letter queue.",
)

DATABASE_URL = os.getenv("WEBHOOK_DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/galaxy")
AUTHORITY_EVENTS_URL = os.getenv("WEBHOOK_AUTHORITY_EVENTS_URL", "http://authority-chain:1317/galaxy/v1/events")
POLL_INTERVAL_SECONDS = int(os.getenv("WEBHOOK_POLL_INTERVAL_SECONDS", "5"))
REQUEST_TIMEOUT = float(os.getenv("WEBHOOK_REQUEST_TIMEOUT", "5"))
MAX_RETRIES = int(os.getenv("WEBHOOK_MAX_RETRIES", "4"))
BACKOFF_BASE_SECONDS = float(os.getenv("WEBHOOK_BACKOFF_BASE_SECONDS", "0.5"))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

_stop = threading.Event()
_worker: threading.Thread | None = None
_seen_tx: set[str] = set()
_debug_received: list[dict[str, Any]] = []

# Prometheus metrics
deliveries_success_counter = Counter('webhook_service_deliveries_success_total', 'Total successful webhook deliveries')
deliveries_failed_counter = Counter('webhook_service_deliveries_failed_total', 'Total failed webhook deliveries')
dead_letters_counter = Counter('webhook_service_dead_letters_total', 'Total dead-lettered webhooks')


class WebhookRegistration(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    target_url: str = Field(..., min_length=1)
    enabled: bool = True


class RetryPolicy(BaseModel):
    max_retries: int = Field(default=MAX_RETRIES, ge=1, le=10)
    timeout_seconds: float = Field(default=REQUEST_TIMEOUT, gt=0)


class DeliveryResult(BaseModel):
    tenant_id: str
    target_url: str
    tx_hash: str
    delivered: bool
    attempts: int


def db_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    id SERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_delivery_logs (
                    id SERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    delivered BOOLEAN NOT NULL,
                    attempts INTEGER NOT NULL,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_dead_letters (
                    id SERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
        conn.commit()


def _subscriptions() -> list[dict[str, Any]]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, target_url, enabled
                FROM webhook_subscriptions
                ORDER BY id ASC;
                """
            )
            rows = cur.fetchall()

    return [
        {
            "tenant_id": row[0],
            "target_url": row[1],
            "enabled": bool(row[2]),
        }
        for row in rows
        if row[2]
    ]


def _record_delivery(result: DeliveryResult, last_error: str = "") -> None:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO webhook_delivery_logs(tenant_id, target_url, tx_hash, delivered, attempts, last_error, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    result.tenant_id,
                    result.target_url,
                    result.tx_hash,
                    result.delivered,
                    result.attempts,
                    last_error,
                    datetime.now(timezone.utc),
                ),
            )
        conn.commit()


def _record_dead_letter(tenant_id: str, target_url: str, tx_hash: str, payload: dict[str, Any], error_message: str) -> None:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO webhook_dead_letters(tenant_id, target_url, tx_hash, payload_json, error_message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    tenant_id,
                    target_url,
                    tx_hash,
                    json.dumps(payload),
                    error_message,
                    datetime.now(timezone.utc),
                ),
            )
        conn.commit()


def _deliver_one(subscription: dict[str, Any], event: dict[str, Any], policy: RetryPolicy) -> DeliveryResult:
    tenant_id = subscription["tenant_id"]
    target_url = subscription["target_url"]
    tx_hash = str(event.get("tx_hash", ""))
    attempts = 0
    last_error = ""

    payload = {
        "tenant_id": tenant_id,
        "source": "galaxy-authority",
        "event": event,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }

    for retry in range(policy.max_retries):
        attempts = retry + 1
        try:
            resp = requests.post(target_url, json=payload, timeout=policy.timeout_seconds)
            if resp.status_code < 300:
                result = DeliveryResult(
                    tenant_id=tenant_id,
                    target_url=target_url,
                    tx_hash=tx_hash,
                    delivered=True,
                    attempts=attempts,
                )
                _record_delivery(result)
                deliveries_success_counter.inc()
                return result
            last_error = f"status={resp.status_code} body={resp.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)

        threading.Event().wait(BACKOFF_BASE_SECONDS * (2 ** retry))

    result = DeliveryResult(
        tenant_id=tenant_id,
        target_url=target_url,
        tx_hash=tx_hash,
        delivered=False,
        attempts=attempts,
    )
    _record_delivery(result, last_error=last_error)
    _record_dead_letter(tenant_id, target_url, tx_hash, payload, last_error or "unknown error")
    deliveries_failed_counter.inc()
    dead_letters_counter.inc()
    return result


def _fetch_events() -> list[dict[str, Any]]:
    try:
        resp = requests.get(
            AUTHORITY_EVENTS_URL,
            params={"limit": 200},
            headers={"X-Internal-Auth": INTERNAL_API_KEY} if INTERNAL_API_KEY else None,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("events", [])
        logger.warning("authority query returned status=%s", resp.status_code)
    except requests.RequestException as exc:
        logger.error("authority query failed: %s", exc)
    return []


def _worker_loop() -> None:
    logger.info("webhook delivery loop started poll_interval=%ds", POLL_INTERVAL_SECONDS)
    policy = RetryPolicy()

    while not _stop.is_set():
        events = _fetch_events()
        verified = [e for e in events if e.get("status") == "verified"]
        subscriptions = _subscriptions()

        for event in reversed(verified):
            tx_hash = str(event.get("tx_hash", ""))
            if not tx_hash or tx_hash in _seen_tx:
                continue

            _seen_tx.add(tx_hash)
            for sub in subscriptions:
                result = _deliver_one(sub, event, policy)
                if result.delivered:
                    logger.info(
                        "webhook delivered tenant=%s tx=%s attempts=%d",
                        sub["tenant_id"],
                        tx_hash,
                        result.attempts,
                    )
                else:
                    logger.error(
                        "webhook failed tenant=%s tx=%s attempts=%d",
                        sub["tenant_id"],
                        tx_hash,
                        result.attempts,
                    )

        _stop.wait(POLL_INTERVAL_SECONDS)

    logger.info("webhook delivery loop stopped")


@app.on_event("startup")
def startup() -> None:
    global _worker
    init_db()
    if _worker and _worker.is_alive():
        return

    _stop.clear()
    _worker = threading.Thread(target=_worker_loop, daemon=True)
    _worker.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _stop.set()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "webhook-delivery",
        "authority_events_url": AUTHORITY_EVENTS_URL,
        "known_events": len(_seen_tx),
        "worker_running": bool(_worker and _worker.is_alive()),
    }


@app.post("/webhooks/register")
def register_webhook(req: WebhookRegistration) -> dict[str, Any]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO webhook_subscriptions(tenant_id, target_url, enabled, created_at)
                VALUES (%s, %s, %s, %s);
                """,
                (req.tenant_id, req.target_url, req.enabled, datetime.now(timezone.utc)),
            )
        conn.commit()

    return {"status": "ok", "tenant_id": req.tenant_id, "target_url": req.target_url, "enabled": req.enabled}


@app.get("/webhooks/subscriptions")
def list_subscriptions() -> dict[str, Any]:
    return {"items": _subscriptions()}


@app.get("/webhooks/dead-letters")
def dead_letters(limit: int = 20) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, target_url, tx_hash, payload_json, error_message, created_at
                FROM webhook_dead_letters
                ORDER BY id DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    items = [
        {
            "tenant_id": row[0],
            "target_url": row[1],
            "tx_hash": row[2],
            "payload": json.loads(row[3]),
            "error_message": row[4],
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


@app.post("/debug/mock-receiver")
def debug_mock_receiver(payload: dict[str, Any]) -> dict[str, Any]:
    _debug_received.insert(0, payload)
    if len(_debug_received) > 200:
        del _debug_received[200:]
    return {"status": "accepted"}


@app.get("/debug/received")
def debug_received(limit: int = 20) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")
    return {"items": _debug_received[:limit], "count": min(limit, len(_debug_received))}


@app.get("/metrics")
def metrics():
    return generate_latest()
