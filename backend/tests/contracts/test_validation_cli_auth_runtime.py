"""Runtime checks for validation CLI device auth/session flows."""

from __future__ import annotations

import base64
import hmac
import json
import os
import time

from fastapi.testclient import TestClient

from src.main import app


_JWT_SECRET = os.environ.setdefault("PLATFORM_AUTH_JWT_HS256_SECRET", "test-validation-cli-auth-secret")


def _jwt_segment(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _jwt_token(payload: dict[str, object]) -> str:
    claims_payload = dict(payload)
    claims_payload.setdefault("exp", int(time.time()) + 300)
    header = _jwt_segment({"alg": "HS256", "typ": "JWT"})
    claims = _jwt_segment(claims_payload)
    signing_input = f"{header}.{claims}".encode("utf-8")
    signature = hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, "sha256").digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{header}.{claims}.{encoded_signature}"


def _user_headers(*, request_id: str, tenant_id: str, user_id: str, user_email: str | None = None) -> dict[str, str]:
    claims: dict[str, object] = {"sub": user_id, "tenant_id": tenant_id}
    if user_email is not None:
        claims["email"] = user_email
    return {
        "Authorization": f"Bearer {_jwt_token(claims)}",
        "X-Request-Id": request_id,
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
    }


def _validation_run_payload() -> dict[str, object]:
    return {
        "strategyId": "strat-001",
        "providerRefId": "lona-strategy-123",
        "prompt": "Build zig-zag strategy for BTC 1h with trend filter",
        "requestedIndicators": ["zigzag", "ema"],
        "datasetIds": ["dataset-btc-1h-2025"],
        "backtestReportRef": "blob://validation/candidate/backtest-report.json",
        "policy": {
            "profile": "STANDARD",
            "blockMergeOnFail": True,
            "blockReleaseOnFail": True,
            "blockMergeOnAgentFail": True,
            "blockReleaseOnAgentFail": False,
            "requireTraderReview": False,
            "hardFailOnMissingIndicators": True,
            "failClosedOnEvidenceUnavailable": True,
        },
    }


def _issue_cli_token(
    client: TestClient,
    *,
    owner_headers: dict[str, str],
    request_suffix: str,
    scopes: list[str] | None = None,
) -> tuple[str, str]:
    start = client.post(
        "/v2/validation-cli-auth/device/start",
        headers={"X-Request-Id": f"req-cli-device-start-{request_suffix}"},
        json={"scopes": scopes} if scopes is not None else {},
    )
    assert start.status_code == 201
    payload = start.json()
    approve = client.post(
        "/v2/validation-cli-auth/device/approve",
        headers={**owner_headers, "X-Request-Id": f"req-cli-device-approve-{request_suffix}"},
        json={"userCode": payload["userCode"]},
    )
    assert approve.status_code == 200
    poll = client.post(
        "/v2/validation-cli-auth/device/token",
        headers={"X-Request-Id": f"req-cli-device-token-{request_suffix}"},
        json={"deviceCode": payload["deviceCode"]},
    )
    assert poll.status_code == 200
    return poll.json()["accessToken"], poll.json()["sessionId"]


def test_cli_device_flow_issues_token_and_allows_whoami_and_validation_reads() -> None:
    client = TestClient(app)
    owner_headers = _user_headers(
        request_id="req-cli-owner-001",
        tenant_id="tenant-cli-runtime-001",
        user_id="user-cli-runtime-001",
        user_email="owner-cli-runtime-001@example.com",
    )
    access_token, _ = _issue_cli_token(client, owner_headers=owner_headers, request_suffix="001")

    whoami = client.get(
        "/v2/validation-cli-auth/whoami",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-Id": "req-cli-whoami-001",
        },
    )
    assert whoami.status_code == 200
    session = whoami.json()["session"]
    assert session["tenantId"] == "tenant-cli-runtime-001"
    assert session["userId"] == "user-cli-runtime-001"

    list_runs = client.get(
        "/v2/validation-runs",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-Id": "req-cli-runs-list-001",
        },
    )
    assert list_runs.status_code == 200


def test_cli_token_with_read_scope_cannot_call_validation_writes() -> None:
    client = TestClient(app)
    owner_headers = _user_headers(
        request_id="req-cli-owner-002",
        tenant_id="tenant-cli-runtime-002",
        user_id="user-cli-runtime-002",
    )
    access_token, _ = _issue_cli_token(
        client,
        owner_headers=owner_headers,
        request_suffix="002",
        scopes=["validation:read"],
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-Id": "req-cli-runs-write-denied-001",
            "Idempotency-Key": "idem-cli-runs-write-denied-001",
        },
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 403
    assert create_run.json()["error"]["code"] == "CLI_AUTH_SCOPE_FORBIDDEN"


def test_cli_device_approve_requires_web_authenticated_user_session() -> None:
    client = TestClient(app)
    owner_headers = _user_headers(
        request_id="req-cli-owner-003",
        tenant_id="tenant-cli-runtime-003",
        user_id="user-cli-runtime-003",
        user_email="owner-cli-runtime-003@example.com",
    )
    access_token, _ = _issue_cli_token(client, owner_headers=owner_headers, request_suffix="003")

    start = client.post(
        "/v2/validation-cli-auth/device/start",
        headers={"X-Request-Id": "req-cli-device-start-approve-guard-001"},
        json={},
    )
    assert start.status_code == 201
    user_code = start.json()["userCode"]

    approve_with_cli_token = client.post(
        "/v2/validation-cli-auth/device/approve",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-Id": "req-cli-device-approve-guard-001",
        },
        json={"userCode": user_code},
    )
    assert approve_with_cli_token.status_code == 403
    assert approve_with_cli_token.json()["error"]["code"] == "CLI_AUTH_WEB_LOGIN_REQUIRED"


def test_cli_session_list_and_revoke_are_user_scoped() -> None:
    client = TestClient(app)
    user_a_headers = _user_headers(
        request_id="req-cli-owner-a-001",
        tenant_id="tenant-cli-runtime-004",
        user_id="user-cli-runtime-004-a",
        user_email="owner-cli-runtime-004-a@example.com",
    )
    user_b_headers = _user_headers(
        request_id="req-cli-owner-b-001",
        tenant_id="tenant-cli-runtime-004",
        user_id="user-cli-runtime-004-b",
        user_email="owner-cli-runtime-004-b@example.com",
    )

    _, session_a = _issue_cli_token(client, owner_headers=user_a_headers, request_suffix="004a")
    _, session_b = _issue_cli_token(client, owner_headers=user_b_headers, request_suffix="004b")

    list_a = client.get(
        "/v2/validation-cli-auth/sessions",
        headers={**user_a_headers, "X-Request-Id": "req-cli-sessions-list-a-001"},
    )
    assert list_a.status_code == 200
    listed_a = {item["id"] for item in list_a.json().get("sessions", [])}
    assert session_a in listed_a
    assert session_b not in listed_a

    revoke_b_as_a = client.post(
        f"/v2/validation-cli-auth/sessions/{session_b}/revoke",
        headers={**user_a_headers, "X-Request-Id": "req-cli-session-revoke-cross-user-001"},
    )
    assert revoke_b_as_a.status_code == 404
    assert revoke_b_as_a.json()["error"]["code"] == "CLI_SESSION_NOT_FOUND"


def test_cli_token_rejects_spoofed_identity_headers() -> None:
    client = TestClient(app)
    owner_headers = _user_headers(
        request_id="req-cli-owner-005",
        tenant_id="tenant-cli-runtime-005",
        user_id="user-cli-runtime-005",
        user_email="owner-cli-runtime-005@example.com",
    )
    access_token, _ = _issue_cli_token(client, owner_headers=owner_headers, request_suffix="005")

    spoofed = client.get(
        "/v2/validation-runs",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-Id": "req-cli-spoof-headers-001",
            "X-Tenant-Id": "tenant-cli-runtime-005-other",
            "X-User-Id": "user-cli-runtime-005",
        },
    )
    assert spoofed.status_code == 401
    assert spoofed.json()["error"]["code"] == "AUTH_IDENTITY_MISMATCH"


def test_cli_introspect_returns_inactive_for_invalid_or_foreign_token() -> None:
    client = TestClient(app)
    owner_headers = _user_headers(
        request_id="req-cli-owner-006",
        tenant_id="tenant-cli-runtime-006",
        user_id="user-cli-runtime-006",
        user_email="owner-cli-runtime-006@example.com",
    )

    invalid_introspect = client.post(
        "/v2/validation-cli-auth/introspect",
        headers={**owner_headers, "X-Request-Id": "req-cli-introspect-invalid-001"},
        json={"accessToken": "tnx.cli.clisess-invalid.invalid"},
    )
    assert invalid_introspect.status_code == 200
    assert invalid_introspect.json()["active"] is False

    other_user_headers = _user_headers(
        request_id="req-cli-owner-006-other",
        tenant_id="tenant-cli-runtime-006",
        user_id="user-cli-runtime-006-other",
        user_email="owner-cli-runtime-006-other@example.com",
    )
    other_token, _ = _issue_cli_token(client, owner_headers=other_user_headers, request_suffix="006-other")
    foreign_introspect = client.post(
        "/v2/validation-cli-auth/introspect",
        headers={**owner_headers, "X-Request-Id": "req-cli-introspect-foreign-001"},
        json={"accessToken": other_token},
    )
    assert foreign_introspect.status_code == 200
    assert foreign_introspect.json()["active"] is False
