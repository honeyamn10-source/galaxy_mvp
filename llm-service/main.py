"""
LLM Service - Wraps Ollama API for the Galaxy MVP.

This service provides:
1. Event analysis using DeepSeek LLM (for AI verifier in authority-chain)
2. Chat endpoint (for dashboard or other clients)
3. Health check endpoint

The service calls Ollama API at OLLAMA_URL to run inference on a locally-deployed
DeepSeek model (deepseek-llm:6.7b or deepseek-coder:6.7b).
"""

import json
import logging
import os
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("llm-service")

app = FastAPI(
    title="Galaxy LLM Service",
    version="1.0.0",
    description="Wraps Ollama API for event analysis and chat.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-llm:6.7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")


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
    """Chat request."""
    question: str
    context: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response."""
    answer: str
    model: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    llm_enabled: bool
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_available: bool


def call_ollama(prompt: str) -> Optional[str]:
    """
    Call Ollama API to generate a response.
    
    Args:
        prompt: The prompt to send to the LLM.
    
    Returns:
        The response text, or None if Ollama is unavailable.
    """
    if not LLM_ENABLED:
        logger.warning("LLM is disabled; returning None")
        return None

    try:
        url = f"{OLLAMA_URL}/api/generate"
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        }

        logger.info(
            "Calling Ollama at %s with model %s",
            url,
            OLLAMA_MODEL,
        )

        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("response", "").strip()

    except requests.exceptions.ConnectionError as e:
        logger.error(
            "Failed to connect to Ollama at %s: %s. "
            "Ensure Ollama is running and accessible.",
            OLLAMA_URL,
            e,
        )
        return None
    except requests.exceptions.Timeout:
        logger.error(
            "Ollama request timed out after %d seconds. "
            "Consider increasing OLLAMA_TIMEOUT.",
            OLLAMA_TIMEOUT,
        )
        return None
    except Exception as e:
        logger.error("Unexpected error calling Ollama: %s", e)
        return None


def is_ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        response = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint."""
    ollama_available = is_ollama_available() if LLM_ENABLED else False

    return HealthResponse(
        status="ok",
        service="llm-service",
        llm_enabled=LLM_ENABLED,
        ollama_url=OLLAMA_URL if LLM_ENABLED else None,
        ollama_model=OLLAMA_MODEL if LLM_ENABLED else None,
        ollama_available=ollama_available,
    )


@app.post("/analyze_event", response_model=EventAnalysisResponse)
def analyze_event(req: EventAnalysisRequest) -> EventAnalysisResponse:
    """
    Analyze an event for authenticity using LLM.

    This endpoint receives event details and uses an LLM to assess
    whether the event is likely genuine or suspicious.

    Args:
        req: Event details (type, confidence, device_id, frame_hash, location, context).

    Returns:
        Verdict ("genuine" or "suspicious") with confidence and analysis.
    """
    if not LLM_ENABLED:
        # Fallback: return based on confidence threshold
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="LLM analysis disabled; using confidence threshold.",
            reasoning=f"Confidence score {req.confidence:.2f} is {'above' if req.confidence >= 0.8 else 'below'} 0.8 threshold.",
        )

    # Construct a prompt for the LLM
    prompt = f"""You are a security analyst for an autonomous cognitive system.
Analyze the following event and determine if it is likely genuine or suspicious.

Event Type: {req.event_type}
Reported Confidence: {req.confidence:.2%}
Device ID: {req.device_id or "unknown"}
Frame Hash: {req.frame_hash or "not provided"}
Location: {req.location or "not provided"}
Additional Context: {req.context or "none"}

Based on these details, is this event GENUINE or SUSPICIOUS?
Respond in JSON format with exactly these fields:
- verdict: "genuine" or "suspicious"
- confidence: a number from 0.0 to 1.0
- reasoning: a brief explanation

JSON response only, no other text."""

    logger.info("Analyzing event: type=%s, confidence=%.2f", req.event_type, req.confidence)

    response = call_ollama(prompt)

    if response is None:
        # Fallback to confidence-based decision
        logger.warning("Ollama unavailable; falling back to confidence threshold.")
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="LLM unavailable; used confidence threshold.",
            reasoning=f"Confidence {req.confidence:.2f} {'passed' if req.confidence >= 0.8 else 'failed'} threshold.",
        )

    # Parse LLM response
    try:
        # Try to extract JSON from the response
        # The LLM might include extra text, so we search for JSON
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
        else:
            data = json.loads(response)

        verdict = data.get("verdict", "").lower()
        if verdict not in ("genuine", "suspicious"):
            verdict = "suspicious" if req.confidence < 0.8 else "genuine"

        conf = float(data.get("confidence", req.confidence))
        conf = max(0.0, min(1.0, conf))

        reasoning = data.get("reasoning", "")

        return EventAnalysisResponse(
            verdict=verdict,
            confidence=conf,
            analysis=f"LLM analysis completed. Model: {OLLAMA_MODEL}",
            reasoning=reasoning or "No reasoning provided by LLM.",
        )

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Failed to parse LLM response: %s. Response was: %s", e, response)
        # Fallback to confidence threshold
        verdict = "genuine" if req.confidence >= 0.8 else "suspicious"
        return EventAnalysisResponse(
            verdict=verdict,
            confidence=req.confidence,
            analysis="LLM response parsing failed; used confidence threshold.",
            reasoning=f"Confidence {req.confidence:.2f} determined verdict.",
        )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Chat endpoint for general questions.

    This can be used by the dashboard or other clients.

    Args:
        req: Chat request with a question and optional context.

    Returns:
        Chat response with the LLM's answer.
    """
    if not LLM_ENABLED:
        raise HTTPException(status_code=503, detail="LLM service is disabled.")

    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required and cannot be empty.")

    prompt = req.question
    if req.context:
        prompt = f"Context: {req.context}\n\nQuestion: {req.question}"

    logger.info("Chat request: %s", req.question[:100])

    response = call_ollama(prompt)

    if response is None:
        raise HTTPException(
            status_code=503,
            detail="Ollama is unavailable. Ensure the service is running and accessible.",
        )

    return ChatResponse(
        answer=response,
        model=OLLAMA_MODEL,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("LLM_HOST", "0.0.0.0")
    port = int(os.getenv("LLM_PORT", "8600"))

    logger.info(
        "Starting LLM service on %s:%d (Ollama at %s, model: %s, enabled: %s)",
        host,
        port,
        OLLAMA_URL,
        OLLAMA_MODEL,
        LLM_ENABLED,
    )

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
