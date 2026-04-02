import asyncio
import json
import logging
import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

import grpc
import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("authority-gateway")

app = FastAPI(
    title="Constellation Authority Gateway",
    version="0.4.0",
    description="Phase III local authority gateway exposing Cosmos-like REST and gRPC submission surfaces.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(os.getenv("AUTHORITY_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LOG = DATA_DIR / "events.jsonl"

MAX_IN_MEMORY = int(os.getenv("AUTHORITY_MAX_MEMORY_EVENTS", "10000"))
VOTE_THRESHOLD = int(os.getenv("AUTHORITY_VOTE_THRESHOLD", "2"))
GRPC_ADDR = os.getenv("AUTHORITY_GRPC_ADDR", "0.0.0.0:9090")

# LLM Service configuration (optional)
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "").strip()
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

store: Deque[Dict] = deque(maxlen=MAX_IN_MEMORY)
subscribers: List[WebSocket] = []
store_lock = threading.Lock()
main_loop: asyncio.AbstractEventLoop | None = None
grpc_server: grpc.Server | None = None


class EventPayload(BaseModel):
    device_id: str
    event_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    location: str | None = None
    frame_hash: str | None = None
    signature: str | None = None


class SubmitEventRequest(BaseModel):
    submitter: str
    envelope_id: str
    origin_peer_id: str
    event: EventPayload


def _json_decode(raw: bytes) -> Dict:
    return json.loads(raw.decode("utf-8")) if raw else {}


def _json_encode(payload: Dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def load_existing() -> None:
    if not EVENT_LOG.exists():
        return
    with EVENT_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                store.append(json.loads(line))
            except json.JSONDecodeError:
                continue


def persist_event(event_doc: Dict) -> None:
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event_doc) + "\n")


def _validate_submission(payload: Dict) -> Tuple[str, str, str, Dict]:
    submitter = payload.get("submitter", "").strip()
    envelope_id = payload.get("envelope_id", "").strip()
    origin_peer_id = payload.get("origin_peer_id", "").strip()
    event = payload.get("event")

    if not submitter:
        raise ValueError("submitter is required")
    if not envelope_id:
        raise ValueError("envelope_id is required")
    if not origin_peer_id:
        raise ValueError("origin_peer_id is required")
    if not isinstance(event, dict):
        raise ValueError("event object is required")

    required_fields = ["device_id", "event_type", "confidence"]
    for field in required_fields:
        if field not in event:
            raise ValueError(f"event.{field} is required")

    confidence = event.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
        raise ValueError("event.confidence must be between 0 and 1")

    return submitter, envelope_id, origin_peer_id, event


def call_llm_verifier(event: Dict) -> Optional[Dict]:
    """
    Call the LLM service to analyze the event for authenticity.

    Args:
        event: The event dictionary with device_id, event_type, confidence, etc.

    Returns:
        A dict with 'verdict' ('genuine'/'suspicious') and 'confidence' (float),
        or None if LLM service is unavailable or disabled.
    """
    if not LLM_SERVICE_URL:
        return None

    try:
        url = f"{LLM_SERVICE_URL}/analyze_event"
        payload = {
            "event_type": event.get("event_type", "unknown"),
            "confidence": float(event.get("confidence", 0.5)),
            "device_id": event.get("device_id"),
            "frame_hash": event.get("frame_hash"),
            "location": event.get("location"),
            "context": None,
        }

        logger.debug("Calling LLM verifier at %s", url)

        response = requests.post(
            url,
            json=payload,
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        return {
            "verdict": data.get("verdict", ""),
            "confidence": float(data.get("confidence", 0.5)),
            "analysis": data.get("analysis", ""),
            "reasoning": data.get("reasoning", ""),
        }

    except requests.exceptions.Timeout:
        logger.warning(
            "LLM service timed out after %d seconds. Using confidence threshold.",
            LLM_TIMEOUT,
        )
        return None
    except requests.exceptions.ConnectionError:
        logger.warning(
            "LLM service at %s is unavailable. Using confidence threshold.",
            LLM_SERVICE_URL,
        )
        return None
    except Exception as e:
        logger.warning("Error calling LLM service: %s. Using confidence threshold.", e)
        return None


def ingest_submission(payload: Dict) -> Dict:
    submitter, envelope_id, origin_peer_id, event = _validate_submission(payload)

    with store_lock:
        existing = next((x for x in store if x.get("envelope_id") == envelope_id), None)
        if existing:
            return {
                "code": 0,
                "height": str(existing["height"]),
                "txhash": existing["tx_hash"],
                "status": existing["status"],
            }

        now = datetime.now(timezone.utc).isoformat()
        height = len(store) + 1
        tx_hash = f"TX{height:012d}"

        # Initial status based on confidence
        confidence = float(event.get("confidence", 0.5))
        status = "verified" if confidence >= 0.8 else "pending"
        llm_verdict = None
        llm_analysis = None

        # Try to enhance verification with LLM service
        llm_result = call_llm_verifier(event)
        if llm_result:
            llm_verdict = llm_result.get("verdict", "").lower()
            llm_analysis = llm_result.get("reasoning", "")
            logger.info(
                "LLM verdict for event %s: %s (confidence: %.2f)",
                envelope_id,
                llm_verdict,
                llm_result.get("confidence", 0),
            )

            # If LLM says it's suspicious, downgrade to pending/rejected
            if llm_verdict == "suspicious":
                status = "pending"
                logger.debug("Event marked as suspicious by LLM verifier")

        event_doc = {
            "height": height,
            "tx_hash": tx_hash,
            "submitter": submitter,
            "envelope_id": envelope_id,
            "origin_peer_id": origin_peer_id,
            "event": event,
            "votes_yes": max(VOTE_THRESHOLD, 1),
            "votes_no": 0,
            "status": status,
            "created_at": now,
            "llm_verdict": llm_verdict,
            "llm_analysis": llm_analysis,
        }

        store.append(event_doc)
        persist_event(event_doc)

    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast_tendermint(event_doc), main_loop)

    return {
        "code": 0,
        "height": str(event_doc["height"]),
        "txhash": event_doc["tx_hash"],
        "status": event_doc["status"],
    }


def grpc_submit_event(req: Dict, _: grpc.ServicerContext) -> Dict:
    try:
        return ingest_submission(req)
    except Exception as exc:
        logger.error("gRPC submit failed: %s", exc)
        return {"code": 1, "message": str(exc)}


def grpc_vote_event(req: Dict, _: grpc.ServicerContext) -> Dict:
    frame_hash = str(req.get("frame_hash", ""))
    vote = int(req.get("vote", 0))
    if not frame_hash or vote not in (1, 2):
        return {"code": 1, "message": "frame_hash and vote (1/2) are required"}

    with store_lock:
        target = next((e for e in store if e["event"].get("frame_hash") == frame_hash), None)
        if not target:
            return {"code": 1, "message": "event not found"}
        if vote == 1:
            target["votes_yes"] += 1
        else:
            target["votes_no"] += 1

        if target["votes_yes"] >= VOTE_THRESHOLD and target["votes_yes"] > target["votes_no"]:
            target["status"] = "verified"

    return {"code": 0, "status": "ok"}


def start_grpc_server() -> grpc.Server:
    server = grpc.server(ThreadPoolExecutor(max_workers=12))

    submit_handler = grpc.unary_unary_rpc_method_handler(
        grpc_submit_event,
        request_deserializer=_json_decode,
        response_serializer=_json_encode,
    )
    vote_handler = grpc.unary_unary_rpc_method_handler(
        grpc_vote_event,
        request_deserializer=_json_decode,
        response_serializer=_json_encode,
    )

    generic = grpc.method_handlers_generic_handler(
        "galaxy.galaxy.Msg",
        {
            "SubmitEvent": submit_handler,
            "VoteEvent": vote_handler,
        },
    )

    server.add_generic_rpc_handlers((generic,))
    server.add_insecure_port(GRPC_ADDR)
    server.start()
    logger.info("authority gRPC started on %s", GRPC_ADDR)
    return server


@app.on_event("startup")
async def startup() -> None:
    global main_loop, grpc_server
    main_loop = asyncio.get_running_loop()
    load_existing()
    grpc_server = start_grpc_server()
    logger.info("authority gateway loaded events=%d", len(store))


@app.on_event("shutdown")
async def shutdown() -> None:
    global grpc_server
    if grpc_server:
        grpc_server.stop(grace=2)
        grpc_server = None


def to_cosmos_tx(event_doc: Dict) -> Dict:
    attrs = [
        {"key": "action", "value": "submit_event", "index": True},
        {"key": "module", "value": "galaxy", "index": True},
        {"key": "device_id", "value": event_doc["event"]["device_id"], "index": True},
        {"key": "event_type", "value": event_doc["event"]["event_type"], "index": True},
        {"key": "confidence", "value": str(int(event_doc["event"]["confidence"] * 100)), "index": True},
        {"key": "status", "value": event_doc["status"], "index": True},
        {"key": "submitter", "value": event_doc["submitter"], "index": True},
        {"key": "envelope_id", "value": event_doc["envelope_id"], "index": True},
    ]
    return {
        "tx_response": {
            "txhash": event_doc["tx_hash"],
            "height": str(event_doc["height"]),
            "code": 0,
            "timestamp": event_doc["created_at"],
            "events": [{"type": "message", "attributes": attrs}],
        },
        "tx": {
            "body": {
                "messages": [
                    {
                        "@type": "/galaxy.galaxy.MsgSubmitEvent",
                        "creator": event_doc["submitter"],
                        "device_id": event_doc["event"]["device_id"],
                        "event_type": event_doc["event"]["event_type"],
                        "confidence": int(event_doc["event"]["confidence"] * 100),
                        "frame_hash": event_doc["event"].get("frame_hash", ""),
                        "signature": event_doc["event"].get("signature", ""),
                    }
                ]
            }
        },
    }


async def broadcast_tendermint(event_doc: Dict) -> None:
    if not subscribers:
        return

    payload = {
        "jsonrpc": "2.0",
        "id": "galaxy-sub",
        "result": {
            "query": "tm.event='Tx' AND message.action='submit_event'",
            "data": {
                "type": "tendermint/event/Tx",
                "value": {
                    "TxResult": {
                        "height": str(event_doc["height"]),
                        "result": {
                            "events": {
                                "message.action": ["submit_event"],
                                "message.module": ["galaxy"],
                                "galaxy.device_id": [event_doc["event"]["device_id"]],
                                "galaxy.event_type": [event_doc["event"]["event_type"]],
                                "galaxy.status": [event_doc["status"]],
                                "galaxy.envelope_id": [event_doc["envelope_id"]],
                            }
                        },
                    }
                },
            },
        },
    }

    stale = []
    for ws in subscribers:
        try:
            await ws.send_json(payload)
        except Exception:
            stale.append(ws)

    for ws in stale:
        if ws in subscribers:
            subscribers.remove(ws)


@app.get("/health")
def health() -> Dict:
    llm_available = False
    if LLM_SERVICE_URL:
        try:
            response = requests.get(f"{LLM_SERVICE_URL}/health", timeout=2)
            llm_available = response.status_code == 200
        except Exception:
            pass

    return {
        "status": "ok",
        "service": "constellation-authority-gateway",
        "events": len(store),
        "grpc_addr": GRPC_ADDR,
        "llm_service_url": LLM_SERVICE_URL or "disabled",
        "llm_available": llm_available,
    }


@app.get("/system/health")
def system_health() -> Dict:
    return {
        "authority": "ok",
        "edge": "unknown",
        "swarm": "unknown",
        "events": len(store),
    }


@app.post("/galaxy/v1/events")
async def submit_event(req: SubmitEventRequest) -> Dict:
    try:
        result = ingest_submission(req.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get("/galaxy/v1/events")
def list_events(limit: int = 50) -> Dict:
    rows = list(store)
    rows = rows[-limit:]
    rows.reverse()
    return {
        "events": rows,
        "total": len(store),
    }


@app.get("/cosmos/tx/v1beta1/txs")
def cosmos_txs(limit: int = 50, events: str | None = None) -> Dict:
    rows = list(store)

    if events:
        normalized = events.replace('"', "'")
        want_submit = "message.action='submit_event'" in normalized
        want_module = "message.module='galaxy'" in normalized
        if want_submit:
            rows = [r for r in rows if r.get("event")]
        if want_module:
            rows = [r for r in rows if r.get("event")]

    rows = rows[-limit:]
    rows.reverse()
    txs = [to_cosmos_tx(row) for row in rows]
    return {
        "tx_responses": [item["tx_response"] for item in txs],
        "txs": [item["tx"] for item in txs],
        "pagination": {"total": str(len(store))},
    }


@app.websocket("/websocket")
async def tm_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    subscribers.append(websocket)

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                req = json.loads(msg)
            except json.JSONDecodeError:
                req = None

            if req and req.get("method") == "subscribe":
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": req.get("id", "galaxy-sub"),
                    "result": {},
                })
            else:
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": "ping",
                    "result": {"ok": True},
                })
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in subscribers:
            subscribers.remove(websocket)
