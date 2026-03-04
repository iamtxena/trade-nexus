"""Contract tests for CLI device-flow verification URI configuration.

Validates:
- env key precedence: PLATFORM_CLI_DEVICE_VERIFICATION_URI > CLI_AUTH_VERIFICATION_URI > safe default
- no `.local` fallback in any resolution path
- device/start response shape includes correct verificationUri host/path
"""

from __future__ import annotations

import os
from unittest import mock

from fastapi.testclient import TestClient


def _import_uri_resolver():
    """Import the private helper after env patches are applied."""
    from src.platform_api.services.validation_identity_service import (
        _cli_device_verification_uri,
    )
    return _cli_device_verification_uri


# ------------------------------------------------------------------
# 1. Precedence: canonical key wins over legacy and default
# ------------------------------------------------------------------

def test_canonical_key_takes_precedence_over_legacy() -> None:
    env = {
        "PLATFORM_CLI_DEVICE_VERIFICATION_URI": "https://canonical.example.com/cli",
        "CLI_AUTH_VERIFICATION_URI": "https://legacy.example.com/cli",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        result = _import_uri_resolver()()
    assert result == "https://canonical.example.com/cli"


def test_legacy_key_used_when_canonical_absent() -> None:
    with mock.patch.dict(
        os.environ,
        {"CLI_AUTH_VERIFICATION_URI": "https://legacy.example.com/cli"},
        clear=False,
    ):
        os.environ.pop("PLATFORM_CLI_DEVICE_VERIFICATION_URI", None)
        result = _import_uri_resolver()()
    assert result == "https://legacy.example.com/cli"


def test_safe_default_when_both_keys_absent() -> None:
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PLATFORM_CLI_DEVICE_VERIFICATION_URI", None)
        os.environ.pop("CLI_AUTH_VERIFICATION_URI", None)
        result = _import_uri_resolver()()
    assert result == "https://trade-nexus.lona.agency/cli-access"


def test_whitespace_only_canonical_falls_through_to_legacy() -> None:
    env = {
        "PLATFORM_CLI_DEVICE_VERIFICATION_URI": "   ",
        "CLI_AUTH_VERIFICATION_URI": "https://legacy.example.com/cli",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        result = _import_uri_resolver()()
    assert result == "https://legacy.example.com/cli"


def test_whitespace_only_both_keys_falls_through_to_default() -> None:
    env = {
        "PLATFORM_CLI_DEVICE_VERIFICATION_URI": "  ",
        "CLI_AUTH_VERIFICATION_URI": "  ",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        result = _import_uri_resolver()()
    assert result == "https://trade-nexus.lona.agency/cli-access"


# ------------------------------------------------------------------
# 2. No .local fallback in any resolution path
# ------------------------------------------------------------------

def test_no_local_domain_in_any_resolution_path() -> None:
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PLATFORM_CLI_DEVICE_VERIFICATION_URI", None)
        os.environ.pop("CLI_AUTH_VERIFICATION_URI", None)
        result = _import_uri_resolver()()
    assert ".local" not in result, f"Verification URI must not contain .local: {result}"


# ------------------------------------------------------------------
# 3. device/start response shape
# ------------------------------------------------------------------

def test_device_start_returns_verification_uri_without_local_domain() -> None:
    secret_patch = {
        "PLATFORM_AUTH_JWT_HS256_SECRET": os.environ.get(
            "PLATFORM_AUTH_JWT_HS256_SECRET", "test-uri-contract-secret"
        ),
    }
    with mock.patch.dict(os.environ, secret_patch, clear=False):
        from src.main import app

        client = TestClient(app)
        resp = client.post(
            "/v2/validation-cli-auth/device/start",
            headers={"X-Request-Id": "req-uri-contract-001"},
            json={},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "verificationUri" in body
    assert "verificationUriComplete" in body
    assert ".local" not in body["verificationUri"], (
        f"verificationUri must not contain .local: {body['verificationUri']}"
    )
    assert ".local" not in body["verificationUriComplete"], (
        f"verificationUriComplete must not contain .local: {body['verificationUriComplete']}"
    )
    assert body["verificationUriComplete"].startswith(body["verificationUri"])
