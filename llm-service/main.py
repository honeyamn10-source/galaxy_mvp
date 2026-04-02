import json
import logging
import os
import random
import re
import threading
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("llm-service")

app = FastAPI(
    title="Galaxy LLM Service",
    version="2.0.0",
    description="OpenRouter-backed event analysis and chat service with key fallback.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "30"))
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://localhost")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "galaxy-mvp")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")
_api_keys = [key.strip() for key in os.getenv("OPENROUTER_API_KEYS", "").split(",") if key.strip()]
_key_lock = threading.Lock()
_key_index = 0


class ClassifyRequest(BaseModel):
    event_type: str
    description: str = ""


class EventAnalysisRequest(BaseModel):
    """Request to analyze an event for authenticity."""
    event_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    device_id: Optional[str] = None
    frame_hash: Optional[str] = None
    location: Optional[str] = None
    context: Optional[str] = None


class EventAnalysisResponse(BaseModel):
    """Response from event analysis."""
    verdict: str  # "genuine" or "suspicious"
    confidence: float
    analysis: str
    reasoning: str


class ChatRequest(BaseModel):
    question: Optional[str] = None
    prompt: Optional[str] = None
    context: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response."""
    answer: str
    model: str


class HealthResponse(BaseModel):
    status: str
    service: str
    llm_enabled: bool
    provider: str
    model: str
    keys_configured: int


def _next_key() -> Optional[str]:
    global _key_index
    if not _api_keys:
        return None
    with _key_lock:
        key = _api_keys[_key_index % len(_api_keys)]
        _key_index = (_key_index + 1) % len(_api_keys)
    return key


async def call_openrouter(prompt: str, max_tokens: int = 200) -> tuple[Optional[str], Optional[str]]:
    if not LLM_ENABLED:
        return None, "llm disabled"
    if not _api_keys:
        return None, "no openrouter api keys configured"

    tried = []
    async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
        for _ in range(len(_api_keys)):
            key = _next_key()
            if not key:
                break
            tried.append(key[:10] + "...")

            try:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": OPENROUTER_SITE_URL,
                        "X-Title": OPENROUTER_APP_NAME,
                    },
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return str(content).strip(), None
                    return None, "empty response content"
            except httpx.HTTPError as exc:
                logger.warning("OpenRouter request failed for key %s: %s", key[:10], exc)
                continue

    return None, f"openrouter failed for keys {tried}"


def _extract_json_block(text: str) -> Optional[dict[str, Any]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _clamp_adjustment(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-0.2, min(0.2, f))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="llm-service",
        llm_enabled=LLM_ENABLED,
        provider="openrouter",
        model=OPENROUTER_MODEL,
        keys_configured=len(_api_keys),
    )


@app.post("/analyze_event", response_model=EventAnalysisResponse)
async def analyze_event(req: EventAnalysisRequest) -> EventAnalysisResponse:
    if not LLM_ENABLED:
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="LLM disabled",
            reasoning="fallback by confidence threshold",
        )

    prompt = (
        "You are a security analyst. Return JSON only with fields verdict, confidence, reasoning. "
        f"event_type={req.event_type}; confidence={req.confidence:.3f}; "
        f"device_id={req.device_id or 'unknown'}; frame_hash={req.frame_hash or 'none'}; "
        f"location={req.location or 'none'}; context={req.context or 'none'}."
    )

    content, error = await call_openrouter(prompt, max_tokens=120)
    if not content:
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="OpenRouter fallback",
            reasoning=error or "provider unavailable",
        )

    try:
        data = _extract_json_block(content) or json.loads(content)

        verdict = str(data.get("verdict", "")).lower()
        if verdict not in ("genuine", "suspicious"):
            verdict = "suspicious" if req.confidence < 0.8 else "genuine"

        conf = float(data.get("confidence", req.confidence))
        conf = max(0.0, min(1.0, conf))

        reasoning = data.get("reasoning", "")

        return EventAnalysisResponse(verdict=verdict, confidence=conf, analysis="OpenRouter", reasoning=reasoning or "n/a")

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Failed to parse OpenRouter response: %s. Content was: %s", e, content)
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="OpenRouter parsing fallback",
            reasoning="fallback by confidence threshold",
        )


@app.post("/classify")
async def classify_event(req: ClassifyRequest) -> dict[str, Any]:
    prompt = (
        "Classify the event and return JSON only with fields confidence_adjustment and reason. "
        "confidence_adjustment must be a float between -0.2 and 0.2. "
        f"event_type={req.event_type}; description={req.description or 'none'}."
    )

    content, error = await call_openrouter(prompt, max_tokens=80)
    if not content:
        return {
            "confidence_adjustment": 0.0,
            "reason": f"fallback: {error or 'provider unavailable'}",
            "model": OPENROUTER_MODEL,
        }

    parsed = _extract_json_block(content)
    if not parsed:
        return {
            "confidence_adjustment": 0.0,
            "reason": "fallback: unparseable model response",
            "model": OPENROUTER_MODEL,
        }

    return {
        "confidence_adjustment": _clamp_adjustment(parsed.get("confidence_adjustment", 0.0)),
        "reason": str(parsed.get("reason", "model-adjusted"))[:200],
        "model": OPENROUTER_MODEL,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not LLM_ENABLED:
        raise HTTPException(status_code=503, detail="LLM service is disabled.")

    question = (req.prompt or req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="prompt or question is required and cannot be empty")

    prompt = question
    if req.context:
        prompt = f"Context: {req.context}\n\nQuestion: {question}"

    logger.info("Chat request: %s", question[:100])

    content, error = await call_openrouter(prompt)

    if not content:
        return ChatResponse(answer=f"LLM fallback response: {error or 'service unavailable'}", model="fallback")

    return ChatResponse(answer=content, model=OPENROUTER_MODEL)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("LLM_HOST", "0.0.0.0")
    port = int(os.getenv("LLM_PORT", "8600"))

    logger.info(
        "Starting LLM service on %s:%d (OpenRouter base=%s model=%s keys=%d enabled=%s)",
        host,
        port,
        OPENROUTER_BASE_URL,
        OPENROUTER_MODEL,
        len(_api_keys),
        LLM_ENABLED,
    )

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
