"""Security tests for validation auth identity derivation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import pytest

from src.platform_api.auth_identity import resolve_validation_identity
from src.platform_api.errors import PlatformAPIError

_JWT_SECRET = os.environ.setdefault("PLATFORM_AUTH_JWT_HS256_SECRET", "test-auth-identity-secret")


def _jwt_segment(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _jwt_token(payload: dict[str, str]) -> str:
    header = _jwt_segment({"alg": "HS256", "typ": "JWT"})
    claims = _jwt_segment(payload)
    signing_input = f"{header}.{claims}".encode("utf-8")
    signature = hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{header}.{claims}.{encoded_signature}"


def test_resolve_validation_identity_uses_verified_jwt_claims() -> None:
    token = _jwt_token(
        {
            "sub": "user-auth-identity-001",
            "tenant_id": "tenant-auth-identity-001",
            "email": "auth-user@example.com",
        }
    )
    identity = resolve_validation_identity(
        authorization=f"Bearer {token}",
        api_key=None,
        tenant_header="tenant-auth-identity-001",
        user_header="user-auth-identity-001",
        request_id="req-auth-identity-verified-001",
    )
    assert identity.user_id == "user-auth-identity-001"
    assert identity.tenant_id == "tenant-auth-identity-001"
    assert identity.user_email == "auth-user@example.com"


def test_resolve_validation_identity_rejects_unsigned_jwt_payload_claims() -> None:
    unsigned = (
        f"{_jwt_segment({'alg': 'none', 'typ': 'JWT'})}."
        f"{_jwt_segment({'sub': 'forged-user', 'tenant_id': 'forged-tenant'})}."
    )
    with pytest.raises(PlatformAPIError) as exc:
        resolve_validation_identity(
            authorization=f"Bearer {unsigned}",
            api_key=None,
            tenant_header="forged-tenant",
            user_header="forged-user",
            request_id="req-auth-identity-unsigned-001",
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "AUTH_UNAUTHORIZED"


def test_resolve_validation_identity_rejects_tampered_jwt_signature() -> None:
    token = _jwt_token({"sub": "user-auth-identity-002", "tenant_id": "tenant-auth-identity-002"})
    header_segment, _, signature_segment = token.split(".")
    tampered_payload = _jwt_segment({"sub": "user-auth-identity-002", "tenant_id": "tenant-auth-identity-999"})
    tampered = f"{header_segment}.{tampered_payload}.{signature_segment}"
    with pytest.raises(PlatformAPIError) as exc:
        resolve_validation_identity(
            authorization=f"Bearer {tampered}",
            api_key=None,
            tenant_header="tenant-auth-identity-999",
            user_header="user-auth-identity-002",
            request_id="req-auth-identity-tampered-001",
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "AUTH_UNAUTHORIZED"


def test_resolve_validation_identity_rejects_spoofed_identity_headers() -> None:
    token = _jwt_token({"sub": "user-auth-identity-003", "tenant_id": "tenant-auth-identity-003"})
    with pytest.raises(PlatformAPIError) as exc:
        resolve_validation_identity(
            authorization=f"Bearer {token}",
            api_key=None,
            tenant_header="tenant-auth-identity-other",
            user_header="user-auth-identity-003",
            request_id="req-auth-identity-spoof-001",
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "AUTH_IDENTITY_MISMATCH"
