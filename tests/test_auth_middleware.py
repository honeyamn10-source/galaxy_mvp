import importlib.util
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

MODULE_PATH = Path(__file__).parents[1] / "shared" / "auth_middleware.py"
spec = importlib.util.spec_from_file_location("auth_middleware", MODULE_PATH)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def test_rejects_placeholder_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "change-me")
    with pytest.raises(HTTPException) as exc:
        auth.decode_access_token("anything")
    assert exc.value.status_code == 503


def test_decodes_valid_access_token(monkeypatch):
    secret = "a-secure-test-secret-that-is-longer-than-32-bytes"
    monkeypatch.setenv("JWT_SECRET", secret)
    token = jwt.encode({"sub": "user-1", "org_id": "org-1", "type": "access"}, secret, algorithm="HS256")
    assert auth.decode_access_token(token)["org_id"] == "org-1"


def test_internal_auth_uses_required_config(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "another-secure-test-secret-over-32-characters")
    assert auth.require_internal_auth("another-secure-test-secret-over-32-characters")["internal"] is True
    with pytest.raises(HTTPException) as exc:
        auth.require_internal_auth("wrong")
    assert exc.value.status_code == 401
