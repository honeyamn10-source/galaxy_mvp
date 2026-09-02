import hmac
import os

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
_security = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32 or secret.startswith(("CHANGE_ME", "change-me")):
        raise HTTPException(status_code=503, detail="Authentication service is not configured")
    return secret


def _internal_key() -> str:
    key = os.getenv("INTERNAL_API_KEY", "")
    if len(key) < 32 or key.startswith(("CHANGE_ME", "change-me")):
        raise HTTPException(status_code=503, detail="Internal authentication is not configured")
    return key


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    return payload


def require_access_token(creds: HTTPAuthorizationCredentials = Depends(_security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_access_token(creds.credentials)


def require_internal_auth(internal_key: str | None = None) -> dict:
    if not internal_key or not hmac.compare_digest(internal_key, _internal_key()):
        raise HTTPException(status_code=401, detail="Internal authentication required")
    return {"sub": "internal", "org_id": "internal", "role": "internal", "internal": True}


def require_request_context(
    creds: HTTPAuthorizationCredentials = Depends(_security),
    x_internal_auth: str | None = Header(default=None, alias="X-Internal-Auth"),
) -> dict:
    if x_internal_auth:
        return require_internal_auth(x_internal_auth)
    if creds:
        payload = decode_access_token(creds.credentials)
        payload["internal"] = False
        return payload
    raise HTTPException(status_code=401, detail="Authorization header required")


def get_org_id(payload: dict = Depends(require_access_token)) -> str:
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=401, detail="org_id missing from token")
    return org_id


def require_role(*roles: str):
    def checker(payload: dict = Depends(require_access_token)):
        if payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Required role: {list(roles)}")
        return payload

    return checker