import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("fl-aggregator")

app = FastAPI(
    title="Galaxy FL Aggregator",
    version="0.4.0",
    description="Phase IV federated learning aggregator using FedAvg with model version persistence.",
)

DATABASE_URL = os.getenv("FL_DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/galaxy")
MODEL_DIR = Path(os.getenv("FL_MODEL_DIR", "/data/fl-models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)
INITIAL_MODEL_SIZE = int(os.getenv("FL_MODEL_SIZE", "32"))
MIN_UPDATES_FOR_AGG = int(os.getenv("FL_MIN_UPDATES_FOR_AGG", "2"))
MAX_PENDING_UPDATES = int(os.getenv("FL_MAX_PENDING_UPDATES", "200"))
AGGREGATION_TOKEN = os.getenv("FL_AUTH_TOKEN", "")

pending_updates: list[dict] = []
current_version = 1
current_weights = np.zeros(INITIAL_MODEL_SIZE, dtype=np.float32)

# Prometheus metrics
aggregation_counter = Counter('fl_aggregator_aggregations_total', 'Total model aggregations performed')
updates_received_counter = Counter('fl_aggregator_updates_received_total', 'Total model updates received from clients')
model_version_gauge = Gauge('fl_aggregator_model_version', 'Current global model version')
pending_updates_gauge = Gauge('fl_aggregator_pending_updates', 'Number of pending model updates')


class ModelUpdateRequest(BaseModel):
    client_id: str
    weights: list[float] = Field(..., min_length=1)
    sample_count: int = Field(..., ge=1)
    token: Optional[str] = None


class ModelMetadata(BaseModel):
    version: int
    created_at: str
    sample_count: int
    model_path: str


class ModelLatestResponse(BaseModel):
    version: int
    weights: list[float]
    metadata: Optional[ModelMetadata] = None


def _db_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fl_model_versions (
                    version INTEGER PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL,
                    sample_count INTEGER NOT NULL,
                    model_path TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fl_model_updates (
                    id SERIAL PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    weights_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
        conn.commit()


def _save_model(version: int, weights: np.ndarray, sample_count: int) -> None:
    model_path = MODEL_DIR / f"global_model_v{version}.json"
    model_path.write_text(json.dumps(weights.tolist()), encoding="utf-8")

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fl_model_versions(version, created_at, sample_count, model_path)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (version) DO NOTHING;
                """,
                (version, datetime.now(timezone.utc), sample_count, str(model_path)),
            )
        conn.commit()


def _latest_metadata() -> Optional[ModelMetadata]:
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT version, created_at, sample_count, model_path
                FROM fl_model_versions
                ORDER BY version DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            return ModelMetadata(
                version=row[0],
                created_at=row[1].isoformat(),
                sample_count=row[2],
                model_path=row[3],
            )


def _maybe_aggregate() -> None:
    global current_version, current_weights

    if len(pending_updates) < MIN_UPDATES_FOR_AGG:
        return

    total_samples = sum(item["sample_count"] for item in pending_updates)
    if total_samples <= 0:
        logger.warning("Skipping aggregation due to zero sample total")
        return

    weighted = np.zeros_like(current_weights, dtype=np.float32)
    for update in pending_updates:
        w = np.array(update["weights"], dtype=np.float32)
        if w.shape != current_weights.shape:
            logger.warning("Skipping update from %s due to mismatched shape", update["client_id"])
            continue
        weighted += w * (update["sample_count"] / total_samples)
    
    aggregation_counter.inc()
    model_version_gauge.set(current_version)
    
    current_version += 1
    current_weights = weighted.astype(np.float32)

    _save_model(current_version, current_weights, total_samples)
    pending_updates.clear()
    logger.info("Aggregated global model version=%d total_samples=%d", current_version, total_samples)


@app.on_event("startup")
def startup() -> None:
    global current_version, current_weights

    init_db()
    metadata = _latest_metadata()
    if metadata and Path(metadata.model_path).exists():
        try:
            current_weights = np.array(
                json.loads(Path(metadata.model_path).read_text(encoding="utf-8")),
                dtype=np.float32,
            )
            current_version = metadata.version
        except Exception as exc:
            logger.warning("Failed loading latest model from disk: %s", exc)

    _save_model(current_version, current_weights, sample_count=0)
    logger.info("FL aggregator started model_version=%d", current_version)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "fl-aggregator",
     


@app.get("/metrics")
def metrics():
    model_version_gauge.set(current_version)
    pending_updates_gauge.set(len(pending_updates))
    return generate_latest()   "model_version": current_version,
        "pending_updates": len(pending_updates),
    }


@app.get("/fl/model/latest", response_model=ModelLatestResponse)
def model_latest() -> ModelLatestResponse:
    return ModelLatestResponse(
        version=current_version,
        weights=current_weights.tolist(),
        metadata=_latest_metadata(),
    )


@app.post("/fl/model/update")
def model_update(req: ModelUpdateRequest) -> dict:
    if AGGREGATION_TOKEN and req.token != AGGREGATION_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    if len(req.weights) != len(current_weights):
        raise HTTPException(
            status_code=400,
            detail=f"weights length must be {len(current_weights)}",
        )

    updates_received_counter.inc()
    if len(pending_updates) >= MAX_PENDING_UPDATES:
        raise HTTPException(status_code=429, detail="pending update queue full")

    update = {
        "client_id": req.client_id,
        "sample_count": req.sample_count,
        "weights": req.weights,
    }
    pending_updates.append(update)

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fl_model_updates(client_id, sample_count, weights_json, created_at)
                VALUES (%s, %s, %s, %s);
                """,
                (req.client_id, req.sample_count, json.dumps(req.weights), datetime.now(timezone.utc)),
            )
        conn.commit()

    _maybe_aggregate()

    return {
        "status": "accepted",
        "client_id": req.client_id,
        "pending_updates": len(pending_updates),
        "current_version": current_version,
    }
