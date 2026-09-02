"""Backward-compatible imports for services using the original module name."""

from shared.security import (  # noqa: F401
    ALGORITHM,
    configure_cors,
    cors_origins,
    decode_access_token,
    get_org_id,
    prometheus_response,
    require_access_token,
    require_internal_auth,
    require_request_context,
    require_role,
    require_user_context,
    required_secret,
    validate_required_secrets,
)

__all__ = [
    "ALGORITHM",
    "configure_cors",
    "cors_origins",
    "decode_access_token",
    "get_org_id",
    "prometheus_response",
    "require_access_token",
    "require_internal_auth",
    "require_request_context",
    "require_role",
    "require_user_context",
    "required_secret",
    "validate_required_secrets",
]
