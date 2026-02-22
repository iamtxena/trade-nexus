"""Authentication and identity derivation helpers for Platform API routes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from src.platform_api.errors import PlatformAPIError


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """Identity resolved from authenticated request credentials."""

    tenant_id: str
    user_id: str
    user_email: str | None = None


def resolve_validation_identity(
    *,
    authorization: str | None,
    api_key: str | None,
    tenant_header: str | None,
    user_header: str | None,
    request_id: str,
) -> AuthenticatedIdentity:
    """Resolve request identity from authenticated credentials for validation routes."""
    identity: AuthenticatedIdentity | None = None

    bearer_token = _parse_bearer_token(authorization)
    if bearer_token is not None:
        identity = _identity_from_bearer_claims(bearer_token)

    normalized_api_key = _non_empty(api_key)
    if identity is None and normalized_api_key is not None:
        identity = _identity_from_api_key(normalized_api_key)

    if identity is None:
        raise PlatformAPIError(
            status_code=401,
            code="AUTH_UNAUTHORIZED",
            message="Authentication required for validation endpoints.",
            request_id=request_id,
        )

    _assert_no_identity_spoofing(
        expected_value=identity.tenant_id,
        provided_value=tenant_header,
        header_name="X-Tenant-Id",
        request_id=request_id,
    )
    _assert_no_identity_spoofing(
        expected_value=identity.user_id,
        provided_value=user_header,
        header_name="X-User-Id",
        request_id=request_id,
    )
    return identity


def _parse_bearer_token(authorization: str | None) -> str | None:
    raw = _non_empty(authorization)
    if raw is None:
        return None
    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return _non_empty(token)


def _identity_from_bearer_claims(token: str) -> AuthenticatedIdentity | None:
    claims = _decode_jwt_payload(token)
    if claims is None:
        return None

    user_id = _claim_value(claims, keys=("user_id", "userId", "sub"))
    if user_id is None:
        return None

    tenant_id = _claim_value(claims, keys=("tenant_id", "tenantId", "org_id", "orgId"))
    if tenant_id is None:
        tenant_id = f"tenant-clerk-{user_id}"
    user_email = _claim_value(
        claims,
        keys=("email", "email_address", "user_email", "userEmail"),
    )
    if user_email is not None:
        user_email = user_email.lower()
    return AuthenticatedIdentity(
        tenant_id=tenant_id,
        user_id=user_id,
        user_email=user_email,
    )


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_segment = parts[1]
    try:
        padded = payload_segment + ("=" * (-len(payload_segment) % 4))
        decoded = base64.urlsafe_b64decode(padded)
    except (ValueError, binascii.Error):
        return None
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _claim_value(payload: dict[str, Any], *, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _identity_from_api_key(api_key: str) -> AuthenticatedIdentity:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return AuthenticatedIdentity(
        tenant_id=f"tenant-apikey-{digest[:12]}",
        user_id=f"user-apikey-{digest[12:24]}",
        user_email=None,
    )


def _assert_no_identity_spoofing(
    *,
    expected_value: str,
    provided_value: str | None,
    header_name: str,
    request_id: str,
) -> None:
    normalized = _non_empty(provided_value)
    if normalized is None:
        return
    if normalized == expected_value:
        return
    raise PlatformAPIError(
        status_code=401,
        code="AUTH_IDENTITY_MISMATCH",
        message=f"{header_name} does not match authenticated identity.",
        request_id=request_id,
        details={
            "header": header_name,
            "reason": "identity_header_mismatch",
        },
    )
