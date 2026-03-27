from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# ========== Event Models ==========

class DetectionEventCreate(BaseModel):
    """Incoming detection from edge planet."""
    device_id: str
    event_type: str  # "fire", "smoke", "intrusion", etc.
    confidence: float = Field(..., ge=0.0, le=1.0)
    location: Optional[str] = None
    frame_hash: Optional[str] = None  # hex-encoded hash
    signature: Optional[str] = None    # hex-encoded signature
    bounding_boxes: Optional[List[dict]] = None  # metadata about detections


class EventResponse(BaseModel):
    """Verified event returned to client."""
    id: str
    tenant_id: str
    device_id: str
    event_type: str
    confidence: float
    location: Optional[str]
    verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Paginated list of events."""
    items: List[EventResponse]
    total: int
    page: int
    page_size: int


# ========== Tenant Models ==========

class TenantCreate(BaseModel):
    """Create new tenant/organization."""
    name: str
    quota_events_per_day: int = 10000


class TenantResponse(BaseModel):
    """Tenant details (non-sensitive)."""
    id: str
    name: str
    balance: float
    quota_events_per_day: int
    events_today: int
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TenantSecretResponse(TenantResponse):
    """Tenant with API key (only shown at creation)."""
    api_key: str


# ========== Device Models ==========

class DeviceCreate(BaseModel):
    """Register a new edge planet device."""
    name: str
    device_type: str = "jetson"
    location: Optional[str] = None
    public_key: str  # PEM-encoded public key


class DeviceResponse(BaseModel):
    """Device info."""
    id: str
    name: str
    device_type: str
    location: Optional[str]
    status: str
    last_heartbeat: Optional[datetime]
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ========== API Key Authentication ==========

class APIKeyRequest(BaseModel):
    """Extract API key from header during request."""
    pass
