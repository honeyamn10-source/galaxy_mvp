import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("compliance-engine")

app = FastAPI(
    title="Galaxy Compliance Engine",
    version="0.5.0",
    description="Phase V policy engine for GDPR/HIPAA/NIST controls before authority storage.",
)

DEFAULT_REGION = os.getenv("COMPLIANCE_DEFAULT_REGION", "eu")
HIPAA_EVENT_TYPES = set(
    item.strip().lower()
    for item in os.getenv("COMPLIANCE_HIPAA_EVENT_TYPES", "health_alert,patient_fall").split(",")
    if item.strip()
)
PII_KEYS = [
    item.strip()
    for item in os.getenv("COMPLIANCE_PII_KEYS", "name,face_id,person_name").split(",")
    if item.strip()
]
ENCRYPTION_KEY = os.getenv("COMPLIANCE_ENCRYPTION_KEY", "phase-v-key")
AUDIT_LOG_PATH = Path(os.getenv("COMPLIANCE_AUDIT_LOG_PATH", "/data/compliance-audit.jsonl"))
AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("COMPLIANCE_DATABASE_URL", "")

# Prometheus metrics
transforms_processed_counter = Counter('compliance_engine_transforms_processed_total', 'Total compliance transformations processed')
policies_applied_counter = Counter('compliance_engine_policies_applied_total', 'Total compliance policies applied', ['policy_name'])
audit_logs_written_counter = Counter('compliance_engine_audit_logs_written_total', 'Total audit log entries written')


class TransformRequest(BaseModel):
    tenant: str = Field(..., min_length=1)
    tenant_region: str | None = None
    event: dict[str, Any]


class TransformResponse(BaseModel):
    tenant: str
    tenant_region: str
    applied_policies: list[str]
    event: dict[str, Any]


def db_conn():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)


def _init_db() -> None:
    conn = db_conn()
    if conn is None:
        return
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_audit_logs (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL,
                    tenant TEXT NOT NULL,
                    tenant_region TEXT NOT NULL,
                    policies_json TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL
                );
                """
            )


def _mask_string(value: str) -> str:
    if len(value) <= 2:
        return "**"
    return value[0] + ("*" * (len(value) - 2)) + value[-1]


def _encrypt_value(raw: str) -> str:
    key_hash = hashlib.sha256(ENCRYPTION_KEY.encode("utf-8")).digest()
    src = raw.encode("utf-8")
    out = bytearray()
    for index, byte in enumerate(src):
        out.append(byte ^ key_hash[index % len(key_hash)])
    return base64.b64encode(bytes(out)).decode("utf-8")


def _gdpr_mask(event: dict[str, Any]) -> dict[str, Any]:
    out = dict(event)
    for key in PII_KEYS:
        value = out.get(key)
        if isinstance(value, str) and value:
            out[key] = _mask_string(value)
    return out


def _hipaa_encrypt(event: dict[str, Any]) -> dict[str, Any]:
    out = dict(event)
    raw = json.dumps(out, separators=(",", ":"), sort_keys=True)
    out["payload_encrypted"] = _encrypt_value(raw)
    out["payload_encryption_alg"] = "xor-sha256-demo"
    return out


def _log_audit(
    tenant: str,
    region: str,
    before: dict[str, Any],
    after: dict[str, Any],
    policies: list[str],
) -> None:
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant": tenant,
        "tenant_region": region,
        "policies": policies,
        "before": before,
        "after": after,
        "standard": "NIST-800-53-mock",
    }

    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    
    audit_logs_written_counter.inc()

    conn = db_conn()
    if conn is None:
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO compliance_audit_logs(created_at, tenant, tenant_region, policies_json, before_json, after_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    datetime.now(timezone.utc),
                    tenant,
                    region,
                    json.dumps(policies),
                    json.dumps(before),
                    json.dumps(after),
                ),
            )


@app.on_event("startup")
def startup() -> None:
    _init_db()
    logger.info("compliance engine started default_region=%s", DEFAULT_REGION)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "compliance-engine",
        "default_region": DEFAULT_REGION,
        "audit_log_path": str(AUDIT_LOG_PATH),
    }


@app.post("/transform", response_model=TransformResponse)
def transform(req: TransformRequest) -> TransformResponse:
    tenant_region = (req.tenant_region or DEFAULT_REGION).strip().lower() or DEFAULT_REGION
    event = dict(req.event)
    before = dict(event)
    policies: list[str] = []

    if tenant_region in {"eu", "eea", "uk"}:
        policies_applied_counter.labels(policy_name="gdpr-mask-pii").inc()

    event_type = str(event.get("event_type", "")).strip().lower()
    if event_type in HIPAA_EVENT_TYPES:
        event = _hipaa_encrypt(event)
        policies.append("hipaa-encrypt-event")
        policies_applied_counter.labels(policy_name="hipaa-encrypt-event").inc()

    if not policies:
        policies.append("policy-pass-through")
        policies_applied_counter.labels(policy_name="policy-pass-through").inc()

    try:
        _log_audit(req.tenant, tenant_region, before, event, policies)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to write audit log: {exc}") from exc

    transforms_processed_counter.inc()
    return TransformResponse(
        tenant=req.tenant,
        tenant_region=tenant_region,
        applied_policies=policies,
        event=event,
    )


@app.get("/audit/recent")
def audit_recent(limit: int = 20) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")

    if not AUDIT_LOG_PATH.exists():
        return {"items": [], "count": 0}

    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"items": list(reversed(items)), "count": len(items)}


@app.get("/metrics")
def metrics():
    return generate_latest()
