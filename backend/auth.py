from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db, Tenant


def get_tenant_from_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Extract and validate API key from request header.
    Returns the Tenant object if valid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header"
        )

    tenant = db.query(Tenant).filter(
        Tenant.api_key == x_api_key,
        Tenant.active == True
    ).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or inactive API key"
        )

    return tenant


def check_quota(tenant: Tenant, db: Session) -> bool:
    """
    Check if tenant has quota remaining for today.
    Returns True if quota available.
    """
    if tenant.events_today >= tenant.quota_events_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily quota exceeded ({tenant.quota_events_per_day} events)"
        )
    return True


def verify_device_ownership(
    device_id: str,
    tenant: Tenant,
    db: Session
) -> bool:
    """
    Verify that a device belongs to the requesting tenant.
    """
    from database import Device

    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant.id
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found or does not belong to your tenant"
        )

    return True
