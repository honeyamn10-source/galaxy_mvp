from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from shared import security


def _valid_secret() -> str:
    return "a-secure-test-value-with-more-than-thirty-two-characters"


def test_placeholder_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "change-me-generate-with-openssl-rand-hex-32")
    with pytest.raises(RuntimeError):
        security.required_secret("JWT_SECRET")


def test_wildcard_cors_is_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        security.cors_origins()


def test_access_token_claims_are_verified(monkeypatch):
    secret = _valid_secret()
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("JWT_ISSUER", "galaxy-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "galaxy-api")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-1",
            "org_id": "org-1",
            "role": "admin",
            "type": "access",
            "iss": "galaxy-auth",
            "aud": "galaxy-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": "token-1",
        },
        secret,
        algorithm="HS256",
    )
    assert security.decode_access_token(token)["org_id"] == "org-1"


def test_refresh_token_is_not_accepted_as_access(monkeypatch):
    secret = _valid_secret()
    monkeypatch.setenv("JWT_SECRET", secret)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-1",
            "org_id": "org-1",
            "role": "admin",
            "type": "refresh",
            "iss": "galaxy-auth",
            "aud": "galaxy-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": "token-2",
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        security.decode_access_token(token)
    assert exc_info.value.status_code == 401
