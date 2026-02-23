"""Authentication and identity derivation helpers for Platform API routes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from src.platform_api.errors import PlatformAPIError

_JWT_SECRET_ENV = "PLATFORM_AUTH_JWT_HS256_SECRET"
_JWT_JWKS_JSON_ENV = "PLATFORM_AUTH_JWKS_JSON"
_JWT_JWKS_URL_ENV = "PLATFORM_AUTH_JWKS_URL"
_JWT_ISSUER_ENV = "PLATFORM_AUTH_JWT_ISSUER"
_JWT_AUDIENCE_ENV = "PLATFORM_AUTH_JWT_AUDIENCE"
_CLERK_JWKS_URL_ENV = "CLERK_JWKS_URL"
_CLERK_ISSUER_ENV = "CLERK_ISSUER"
_JWT_TIME_LEEWAY_SECONDS = 15
_RUNTIME_BOT_KEY_PREFIX = "tnx.bot"


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
        if identity is None and _is_jwt_like_token(bearer_token):
            raise PlatformAPIError(
                status_code=401,
                code="AUTH_UNAUTHORIZED",
                message="Bearer token is invalid.",
                request_id=request_id,
            )

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
    claims = _decode_verified_jwt_payload(token)
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


def _is_jwt_like_token(token: str) -> bool:
    return token.count(".") == 2


def _decode_jwt_payload_segment(segment: str) -> dict[str, Any] | None:
    try:
        padded = segment + ("=" * (-len(segment) % 4))
        decoded = base64.urlsafe_b64decode(padded)
    except (ValueError, binascii.Error):
        return None
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _decode_jwt_signature(segment: str) -> bytes | None:
    try:
        padded = segment + ("=" * (-len(segment) % 4))
        return base64.urlsafe_b64decode(padded)
    except (ValueError, binascii.Error):
        return None


def _jwt_secret() -> str | None:
    return _non_empty(os.getenv(_JWT_SECRET_ENV))


def _jwt_issuer() -> str | None:
    return _non_empty(os.getenv(_JWT_ISSUER_ENV)) or _non_empty(os.getenv(_CLERK_ISSUER_ENV))


def _jwt_audience() -> str | list[str] | None:
    raw = _non_empty(os.getenv(_JWT_AUDIENCE_ENV))
    if raw is None:
        return None
    audiences = [value.strip() for value in raw.split(",") if value.strip()]
    if not audiences:
        return None
    if len(audiences) == 1:
        return audiences[0]
    return audiences


def _jwt_jwks_url() -> str | None:
    configured = _non_empty(os.getenv(_JWT_JWKS_URL_ENV)) or _non_empty(os.getenv(_CLERK_JWKS_URL_ENV))
    if configured is not None:
        return configured
    issuer = _jwt_issuer()
    if issuer is None:
        return None
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def _jwt_jwks_payload() -> dict[str, Any] | None:
    raw = _non_empty(os.getenv(_JWT_JWKS_JSON_ENV))
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    keys = payload.get("keys")
    if not isinstance(keys, list):
        return None
    return payload


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(
        jwks_url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


def _claims_time_window_valid(claims: dict[str, Any]) -> bool:
    now = int(time.time())
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    if now >= int(exp) + _JWT_TIME_LEEWAY_SECONDS:
        return False
    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and now + _JWT_TIME_LEEWAY_SECONDS < int(nbf):
        return False
    return True


def _decode_verified_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_segment, payload_segment, signature_segment = parts
    header = _decode_jwt_payload_segment(header_segment)
    if header is None:
        return None

    algorithm = header.get("alg")
    if algorithm == "HS256":
        payload = _decode_jwt_payload_segment(payload_segment)
        if payload is None:
            return None
        return _decode_verified_hs256_payload(
            payload=payload,
            header_segment=header_segment,
            payload_segment=payload_segment,
            signature_segment=signature_segment,
        )
    if algorithm == "RS256":
        return _decode_verified_rs256_payload(token)
    return None


def _decode_verified_hs256_payload(
    *,
    payload: dict[str, Any],
    header_segment: str,
    payload_segment: str,
    signature_segment: str,
) -> dict[str, Any] | None:
    secret = _jwt_secret()
    if secret is None:
        return None

    provided_signature = _decode_jwt_signature(signature_segment)
    if provided_signature is None:
        return None

    signing_input = f"{header_segment}.{payload_segment}".encode()
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None

    if not _claims_time_window_valid(payload):
        return None
    return payload


def _decode_verified_rs256_payload(token: str) -> dict[str, Any] | None:
    signing_key = _jwt_signing_key(token)
    if signing_key is None:
        return None

    issuer = _jwt_issuer()
    audience = _jwt_audience()
    options = {
        "require": ["exp"],
        "verify_aud": audience is not None,
        "verify_iss": issuer is not None,
    }
    try:
        claims = jwt.decode(
            token,
            key=signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            leeway=_JWT_TIME_LEEWAY_SECONDS,
            options=options,
        )
    except InvalidTokenError:
        return None
    return claims if isinstance(claims, dict) else None


def _jwt_signing_key(token: str) -> Any | None:
    jwks_payload = _jwt_jwks_payload()
    if jwks_payload is not None:
        return _jwt_signing_key_from_jwks_payload(token=token, jwks_payload=jwks_payload)

    jwks_url = _jwt_jwks_url()
    if jwks_url is None:
        return None
    try:
        return _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
    except (InvalidTokenError, PyJWKClientError):
        return None


def _jwt_signing_key_from_jwks_payload(
    *,
    token: str,
    jwks_payload: dict[str, Any],
) -> Any | None:
    keys = jwks_payload.get("keys")
    if not isinstance(keys, list):
        return None
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError:
        return None
    kid = header.get("kid")
    candidates = [candidate for candidate in keys if isinstance(candidate, dict)]
    if kid is not None:
        candidates = [candidate for candidate in candidates if candidate.get("kid") == kid]
    elif len(candidates) != 1:
        return None
    if not candidates:
        return None
    for candidate in candidates:
        try:
            return RSAAlgorithm.from_jwk(json.dumps(candidate))
        except (TypeError, ValueError):
            continue
    return None


def _claim_value(payload: dict[str, Any], *, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _identity_from_api_key(api_key: str) -> AuthenticatedIdentity | None:
    if not api_key.startswith(f"{_RUNTIME_BOT_KEY_PREFIX}."):
        return None
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
