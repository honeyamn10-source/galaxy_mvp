"""Security primitives shared by Galaxy's Python services.

The helpers in this module intentionally fail closed. Production services must
receive secrets and browser origins through environment variables; insecure
placeholder values are rejected instead of silently becoming credentials.
"""

from __future__ import annotations

import hmac
import os
from typing import Iterable

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
_security = HTTPBearer(auto_error=False)
_PLACEHOLDER_FRAGMENTS = (
    "change-me",
    "changeme",
    "test1234",
    "edge-planet-local",
    "phase-v-key",
    "example-secret",
)


def environment() -> str:
    return os.getenv("ENVIRONMENT", "production").strip().lower() or "production"


def required_secret(name: str, *, minimum_length: int = 32) -> str:
    value = os.getenv(name, "").strip()
    lowered = value.lower()
    if len(value) < minimum_length or any(fragment in lowered for fragment in _PLACEHOLDER_FRAGMENTS):
        raise RuntimeError(
            f"{name} must be configured with a non-placeholder value of at least "
            f"{minimum_length} characters"
        )
    return value


def validate_required_secrets(names: Iterable[str]) -> None:
    for name in names:
        required_secret(name)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    if "*" in origins:
        if environment() == "production":
            raise RuntimeError("CORS_ALLOWED_ORIGINS cannot contain '*' in production")
        return ["*"]
    return origins


def configure_cors(app) -> None:
    origins = cors_origins()
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Internal-Auth", "X-Request-ID"],
        max_age=600,
    )


def jwt_issuer() -> str:
    return os.getenv("JWT_ISSUER", "galaxy-auth").strip() or "galaxy-auth"


def jwt_audience() -> str:
    return os.getenv("JWT_AUDIENCE", "galaxy-api").strip() or "galaxy-api"


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            required_secret("JWT_SECRET"),
            algorithms=[ALGORITHM],
            issuer=jwt_issuer(),
            audience=jwt_audience(),
            options={"require": ["exp", "iat", "jti", "iss", "aud", "sub", "org_id", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")
    return payload


def require_access_token(
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_access_token(creds.credentials)


def require_internal_auth(
    internal_key: str | None = Header(default=None, alias="X-Internal-Auth"),
) -> dict:
    expected = required_secret("INTERNAL_API_KEY")
    supplied = internal_key or ""
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
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


def require_user_context(payload: dict = Depends(require_access_token)) -> dict:
    payload["internal"] = False
    return payload


def get_org_id(payload: dict = Depends(require_access_token)) -> str:
    org_id = str(payload.get("org_id", "")).strip()
    if not org_id:
        raise HTTPException(status_code=401, detail="org_id missing from token")
    return org_id


def require_role(*roles: str):
    allowed = frozenset(roles)

    def checker(payload: dict = Depends(require_access_token)) -> dict:
        if payload.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return payload

    return checker


def prometheus_response(payload: bytes | str) -> Response:
    return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")
