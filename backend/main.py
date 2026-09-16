from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
import uuid
from datetime import datetime
import json
import redis
import logging
import os
from prometheus_client import Counter, Gauge, generate_latest

from database import init_db, get_db, Event, Tenant, Device
from schemas import (
    DetectionEventCreate,
    EventResponse,
    EventListResponse,
    TenantCreate,
    TenantSecretResponse,
    TenantResponse,
    DeviceCreate,
    DeviceResponse
)
from auth import get_tenant_from_api_key, check_quota, verify_device_ownership

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
events_submitted_counter = Counter('backend_events_submitted_total', 'Total events submitted')
events_verified_counter = Counter('backend_events_verified_total', 'Total events verified')
devices_registered_counter = Counter('backend_devices_registered_total', 'Total devices registered')
tenants_registered_counter = Counter('backend_tenants_registered_total', 'Total tenants registered')


class WebSocketManager:
    """Tracks active dashboard sockets per tenant for real-time push."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(tenant_id, []).append(websocket)

    def disconnect(self, tenant_id: str, websocket: WebSocket):
        sockets = self.connections.get(tenant_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets and tenant_id in self.connections:
            del self.connections[tenant_id]

    async def broadcast(self, tenant_id: str, message: dict):
        sockets = self.connections.get(tenant_id, [])
        stale = []
        for socket in sockets:
            try:
                await socket.send_json(message)
            except Exception:
                stale.append(socket)

        for socket in stale:
            self.disconnect(tenant_id, socket)


ws_manager = WebSocketManager()

# Create FastAPI app
app = FastAPI(
    title="Galaxy Event Detection API",
    description="Phase I: Core event detection and verification system",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis for real-time events
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.warning(f"Redis not available: {e}")
    redis_client = None


def _decode_optional_hex(value: str | None, field_name: str) -> bytes | None:
    """Decode an optional hex field and raise clean 422 errors for bad values."""
    if value is None:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be a valid hex string"
        ) from exc


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")


# ========== HEALTH CHECK ==========

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "galaxy-event-api",
        "phase": "I"
    }


# ========== EVENTS ROUTES ==========

@app.post("/events", response_model=EventResponse, status_code=201)
async def submit_event(
    event: DetectionEventCreate,
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """
    Submit a detection event from an edge planet.

    - Validates tenant quota
    - Verifies device ownership
    - Marks high-confidence events as pre-verified
    - Publishes to Redis for real-time streaming
    - Returns event details
    """
    # Check quota
    check_quota(tenant, db)

    # Verify device ownership
    verify_device_ownership(event.device_id, tenant, db)

    # Create event record
    event_id = str(uuid.uuid4())
    db_event = Event(
        id=event_id,
        tenant_id=tenant.id,
        device_id=event.device_id,
        event_type=event.event_type,
        confidence=event.confidence,
        location=event.location,
        frame_hash=_decode_optional_hex(event.frame_hash, "frame_hash"),
        signature=_decode_optional_hex(event.signature, "signature"),
        # Pre-verify if confidence is high (Phase I simple logic)
        verified=event.confidence >= 0.8
    )

    db.add(db_event)

    # Update tenant quota
    tenant.events_today += 1

    db.commit()
    db.refresh(db_event)

    # Record metrics
    events_submitted_counter.inc()
    if db_event.verified:
        events_verified_counter.inc()

    # Publish to Redis for real-time dashboards
    if redis_client:
        try:
            event_msg = {
                "id": db_event.id,
                "device_id": db_event.device_id,
                "event_type": db_event.event_type,
                "confidence": db_event.confidence,
                "verified": db_event.verified,
                "created_at": db_event.created_at.isoformat()
            }
            redis_client.publish(f"events:{tenant.id}", json.dumps(event_msg))
            logger.info(f"Published event {event_id} to Redis")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    logger.info(f"Event {event_id} recorded for tenant {tenant.id}")

    event_response = EventResponse.from_attributes(db_event)
    await ws_manager.broadcast(tenant.id, event_response.model_dump(mode="json"))

    return event_response


@app.get("/events", response_model=EventListResponse)
def list_events(
    page: int = 1,
    page_size: int = 50,
    verified_only: bool = False,
    event_type: str = None,
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """
    List events for the authenticated tenant.

    - Pagination support
    - Filter by verification status
    - Filter by event type
    """
    query = db.query(Event).filter(Event.tenant_id == tenant.id)

    if verified_only:
        query = query.filter(Event.verified == True)

    if event_type:
        query = query.filter(Event.event_type == event_type)

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    events = query.order_by(desc(Event.created_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return EventListResponse(
        items=[EventResponse.from_attributes(e) for e in events],
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/events/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """Get a specific event by ID (must belong to tenant)."""
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.tenant_id == tenant.id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    return EventResponse.from_attributes(event)


# ========== TENANT ROUTES ==========

@app.post("/tenants", response_model=TenantSecretResponse, status_code=201)
def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new tenant (in production, restricted to admin).
    Returns the API key which should be saved securely.
    """
    # Generate API key
    api_key = f"gal_{uuid.uuid4().hex[:32]}"

    db_tenant = Tenant(
        id=str(uuid.uuid4()),
        name=tenant_data.name,
        api_key=api_key,
        quota_events_per_day=tenant_data.quota_events_per_day
    )

    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)

    logger.info(f"Created tenant {db_tenant.id}: {tenant_data.name}")
    tenants_registered_counter.inc()

    return TenantSecretResponse.from_attributes(db_tenant)


@app.get("/me", response_model=TenantResponse)
def get_current_tenant(
    tenant: Tenant = Depends(get_tenant_from_api_key)
):
    """Get current tenant details (from API key)."""
    return TenantResponse.from_attributes(tenant)


# ========== DEVICE ROUTES ==========

@app.post("/devices", response_model=DeviceResponse, status_code=201)
def register_device(
    device_data: DeviceCreate,
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """Register a new edge planet device for the tenant."""
    db_device = Device(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=device_data.name,
        device_type=device_data.device_type,
        location=device_data.location,
        public_key=device_data.public_key,
        status="offline"
    )

    db.add(db_device)
    db.commit()
    db.refresh(db_device)

    logger.info(f"Registered device {db_device.id} for tenant {tenant.id}")
    devices_registered_counter.inc()

    return DeviceResponse.from_attributes(db_device)


@app.get("/devices", response_model=list[DeviceResponse])
def list_devices(
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """List all devices for the tenant."""
    devices = db.query(Device).filter(
        Device.tenant_id == tenant.id,
        Device.active == True
    ).all()

    return [DeviceResponse.from_attributes(d) for d in devices]


@app.post("/devices/{device_id}/heartbeat", status_code=204)
def device_heartbeat(
    device_id: str,
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db)
):
    """Update device heartbeat and online status."""
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant.id
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    device.last_heartbeat = datetime.utcnow()
    device.status = "online"
    db.commit()

    return None


@app.websocket("/ws")
async def websocket_events(websocket: WebSocket):
    """Authenticated real-time event stream for a tenant dashboard."""
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        await websocket.close(code=1008, reason="Missing api_key")
        return

    db = next(get_db())
    try:
        tenant = db.query(Tenant).filter(
            Tenant.api_key == api_key,
            Tenant.active == True
        ).first()

        if not tenant:
            await websocket.close(code=1008, reason="Invalid API key")
            return

        await ws_manager.connect(tenant.id, websocket)
        logger.info(f"WebSocket connected for tenant {tenant.id}")

        try:
            while True:
                # Keep connection open; clients can optionally send ping messages.
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for tenant {tenant.id}")
        finally:
            ws_manager.disconnect(tenant.id, websocket)
    finally:
        db.close()


@app.get("/metrics")
def metrics():
    return generate_latest()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
