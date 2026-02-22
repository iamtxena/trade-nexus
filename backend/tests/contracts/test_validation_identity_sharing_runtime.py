"""Runtime tests for validation identity linkage and shared-run access controls."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient
import pytest

from src.main import app
from src.platform_api import router_v1 as router_v1_module
from src.platform_api import router_v2 as router_v2_module
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import RequestContext

_JWT_SECRET = os.environ.setdefault("PLATFORM_AUTH_JWT_HS256_SECRET", "test-validation-runtime-secret")


def _client() -> TestClient:
    return TestClient(app)


def _jwt_segment(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _jwt_token(claims: dict[str, str]) -> str:
    header_segment = _jwt_segment({"alg": "HS256", "typ": "JWT"})
    payload_segment = _jwt_segment(claims)
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _auth_headers(
    *,
    request_id: str,
    tenant_id: str,
    user_id: str,
    user_email: str | None = None,
) -> dict[str, str]:
    claims: dict[str, str] = {"sub": user_id, "tenant_id": tenant_id}
    if user_email is not None:
        claims["email"] = user_email
    token = _jwt_token(claims)
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "test-key",
        "X-Request-Id": request_id,
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
    }


def _validation_run_payload() -> dict[str, object]:
    return {
        "strategyId": "strat-001",
        "providerRefId": "lona-strategy-123",
        "prompt": "Validate baseline strategy runtime payload.",
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


def _issue_runtime_invite_code(
    *,
    request_id: str,
    tenant_id: str,
    user_id: str,
    bot_id: str,
    source_ip: str,
) -> str:
    context = RequestContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        owner_user_id=user_id,
        actor_type="user",
        actor_id=user_id,
    )
    invite_code, _ = router_v2_module._identity_service.request_invite_code(  # noqa: SLF001
        context=context,
        bot_id=bot_id,
        source_ip=source_ip,
    )
    return invite_code


@pytest.fixture(autouse=True)
def _reset_runtime_state() -> None:
    identity = router_v2_module._identity_service
    validation = router_v2_module._validation_service
    store = router_v1_module._store

    def _clear() -> None:
        identity._invite_codes.clear()  # noqa: SLF001
        identity._bot_keys.clear()  # noqa: SLF001
        identity._bot_key_index.clear()  # noqa: SLF001
        identity._invite_rate_limit_index.clear()  # noqa: SLF001
        identity._share_invites_by_run.clear()  # noqa: SLF001
        identity._share_grants_by_run.clear()  # noqa: SLF001
        identity._partner_credentials = {}  # noqa: SLF001
        identity._invite_counter = 1  # noqa: SLF001
        identity._key_counter = 1  # noqa: SLF001
        identity._share_counter = 1  # noqa: SLF001

        validation._runs.clear()  # noqa: SLF001
        validation._baselines.clear()  # noqa: SLF001
        validation._replays.clear()  # noqa: SLF001
        validation._run_counter = 1  # noqa: SLF001
        validation._baseline_counter = 1  # noqa: SLF001
        validation._replay_counter = 1  # noqa: SLF001

        for scope in (
            "validation_runs",
            "validation_reviews",
            "validation_renders",
            "validation_baselines",
            "validation_replays",
        ):
            store._idempotency[scope].clear()  # noqa: SLF001

        store.validation_identity_audit_events.clear()

    _clear()
    yield
    _clear()


def test_runtime_bot_partner_registration_resolves_actor_identity_for_validation_runs() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001

    headers = _auth_headers(
        request_id="req-runtime-bot-partner-register-001",
        tenant_id="tenant-runtime-bot",
        user_id="owner-runtime-bot",
    )

    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**headers, "Idempotency-Key": "idem-runtime-bot-partner-register-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot@example.com",
            "botName": "Runtime Bot 1",
        },
    )
    assert register.status_code == 201
    runtime_key = register.json()["issuedKey"]["rawKey"]
    key_id = register.json()["issuedKey"]["key"]["id"]

    rotate = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-partner-register-002",
            "Idempotency-Key": "idem-runtime-bot-partner-register-002",
        },
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot@example.com",
            "botName": "Runtime Bot 1",
        },
    )
    assert rotate.status_code == 201
    runtime_key = rotate.json()["issuedKey"]["rawKey"]
    key_id = rotate.json()["issuedKey"]["key"]["id"]

    revoke = client.post(
        f"/v2/validation-bots/runtime-bot-1/keys/{key_id}/revoke",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-revoke-001",
            "Idempotency-Key": "idem-runtime-bot-revoke-001",
        },
        json={},
    )
    assert revoke.status_code == 200
    assert revoke.json()["key"]["status"] == "revoked"

    reissue = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-partner-register-003",
            "Idempotency-Key": "idem-runtime-bot-partner-register-003",
        },
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot@example.com",
            "botName": "Runtime Bot 1",
        },
    )
    assert reissue.status_code == 201
    runtime_key = reissue.json()["issuedKey"]["rawKey"]

    create_run = client.post(
        "/v2/validation-runs",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-create-run-001",
            "X-API-Key": runtime_key,
            "Idempotency-Key": "idem-runtime-bot-run-001",
        },
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]
    assert create_run.json()["run"]["actor"]["actorType"] == "bot"
    assert create_run.json()["run"]["actor"]["actorId"] == "runtime-bot-1"

    artifact = client.get(
        f"/v2/validation-runs/{run_id}/artifact",
        headers={**headers, "X-Request-Id": "req-runtime-bot-artifact-001"},
    )
    assert artifact.status_code == 200
    assert artifact.json()["artifact"]["userId"] == "owner-runtime-bot"

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_run(  # noqa: SLF001
            run_id=run_id,
            tenant_id="tenant-runtime-bot",
            user_id="owner-runtime-bot",
        )
    )
    assert persisted is not None
    assert persisted.metadata.owner_user_id == "owner-runtime-bot"
    assert persisted.metadata.actor_type == "bot"
    assert persisted.metadata.actor_id == "runtime-bot-1"

    audit_events = router_v1_module._store.validation_identity_audit_events
    assert any(item.event_type == "register" for item in audit_events)
    assert any(item.event_type == "rotate" for item in audit_events)
    assert any(item.event_type == "revoke" for item in audit_events)


def test_runtime_bot_invite_registration_path_is_single_use_and_rate_limited() -> None:
    client = _client()
    tenant_id = "tenant-runtime-bot-invite"
    user_id = "owner-runtime-bot-invite"
    source_ip = "198.51.100.21"
    headers = _auth_headers(
        request_id="req-runtime-bot-invite-001",
        tenant_id=tenant_id,
        user_id=user_id,
    )

    invite_code = _issue_runtime_invite_code(
        request_id="req-runtime-bot-invite-seed-001",
        tenant_id=tenant_id,
        user_id=user_id,
        bot_id="runtime-bot-invite-1",
        source_ip=source_ip,
    )

    register = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-invite-register-001",
            "Idempotency-Key": "idem-runtime-bot-invite-register-001",
        },
        json={
            "inviteCode": invite_code,
            "botName": "Runtime Bot Invite 1",
        },
    )
    assert register.status_code == 201
    assert register.json()["registration"]["registrationPath"] == "invite_code_trial"

    reuse = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers={
            **headers,
            "X-Request-Id": "req-runtime-bot-invite-register-002",
            "Idempotency-Key": "idem-runtime-bot-invite-register-002",
        },
        json={
            "inviteCode": invite_code,
            "botName": "Runtime Bot Invite 1",
        },
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "BOT_INVITE_INVALID"

    _issue_runtime_invite_code(
        request_id="req-runtime-bot-invite-seed-002",
        tenant_id=tenant_id,
        user_id=user_id,
        bot_id="runtime-bot-invite-2",
        source_ip=source_ip,
    )
    _issue_runtime_invite_code(
        request_id="req-runtime-bot-invite-seed-003",
        tenant_id=tenant_id,
        user_id=user_id,
        bot_id="runtime-bot-invite-3",
        source_ip=source_ip,
    )
    with pytest.raises(PlatformAPIError) as exc:
        _issue_runtime_invite_code(
            request_id="req-runtime-bot-invite-seed-004",
            tenant_id=tenant_id,
            user_id=user_id,
            bot_id="runtime-bot-invite-4",
            source_ip=source_ip,
        )
    assert exc.value.status_code == 429
    assert exc.value.code == "BOT_INVITE_RATE_LIMITED"


def test_runtime_identity_routes_require_authenticated_identity() -> None:
    client = _client()

    shared = client.get(
        "/v2/validation-sharing/runs/valrun-0001",
        headers={
            "X-Request-Id": "req-shared-unauth-001",
            "X-Tenant-Id": "tenant-unauth",
            "X-User-Id": "user-unauth",
        },
    )
    assert shared.status_code == 401
    assert shared.json()["error"]["code"] == "AUTH_UNAUTHORIZED"

    register = client.post(
        "/v2/validation-bots/runtime-bot-unauth/keys/rotate",
        headers={
            "X-Request-Id": "req-bot-unauth-001",
            "X-Tenant-Id": "tenant-unauth",
            "X-User-Id": "user-unauth",
            "Idempotency-Key": "idem-bot-unauth-rotate-001",
        },
        json={},
    )
    assert register.status_code == 401
    assert register.json()["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_shared_validation_access_owner_invited_and_denied_users() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-owner-001",
        tenant_id="tenant-shared-validation",
        user_id="owner-shared-validation",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]
    assert create_run.json()["run"]["actor"]["actorType"] == "user"
    assert create_run.json()["run"]["actor"]["actorId"] == "owner-shared-validation"

    share = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-share-001",
            "Idempotency-Key": "idem-shared-validation-share-001",
        },
        json={"email": "invitee@example.com"},
    )
    assert share.status_code == 201

    denied = client.get(
        f"/v2/validation-sharing/runs/{run_id}",
        headers=_auth_headers(
            request_id="req-shared-validation-denied-001",
            tenant_id="tenant-shared-validation",
            user_id="denied-user",
            user_email="other@example.com",
        ),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "VALIDATION_RUN_ACCESS_DENIED"

    invited_headers = _auth_headers(
        request_id="req-shared-validation-invitee-001",
        tenant_id="tenant-shared-validation",
        user_id="invitee-user",
        user_email="invitee@example.com",
    )
    invited_get = client.get(f"/v2/validation-sharing/runs/{run_id}", headers=invited_headers)
    assert invited_get.status_code == 200

    invited_review = client.post(
        f"/v2/validation-sharing/runs/{run_id}/review",
        headers={**invited_headers, "Idempotency-Key": "idem-shared-validation-review-001"},
        json={
            "reviewerType": "agent",
            "decision": "pass",
            "summary": "Shared reviewer accepted evidence.",
            "findings": [],
            "comments": [],
        },
    )
    assert invited_review.status_code == 202

    owner_surface_for_invitee = client.get(
        f"/v2/validation-runs/{run_id}",
        headers={**invited_headers, "X-Request-Id": "req-shared-validation-owner-surface-denied-001"},
    )
    assert owner_surface_for_invitee.status_code == 404
    assert owner_surface_for_invitee.json()["error"]["code"] == "VALIDATION_RUN_NOT_FOUND"

    owner_get = client.get(
        f"/v2/validation-runs/{run_id}",
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-owner-get-001"},
    )
    assert owner_get.status_code == 200

    audit_events = router_v1_module._store.validation_identity_audit_events
    assert any(item.event_type == "share" for item in audit_events)
    assert any(item.event_type == "accept" for item in audit_events)


def test_shared_invite_auto_accepts_on_authenticated_login_email_match() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-auto-accept-owner-001",
        tenant_id="tenant-shared-auto-accept",
        user_id="owner-shared-auto-accept",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-auto-accept-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    share = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-auto-accept-share-001",
            "Idempotency-Key": "idem-shared-auto-accept-share-001",
        },
        json={"email": "login-user@example.com"},
    )
    assert share.status_code == 201

    before_login = client.get(
        f"/v2/validation-sharing/runs/{run_id}",
        headers=_auth_headers(
            request_id="req-shared-auto-accept-before-login-001",
            tenant_id="tenant-shared-auto-accept",
            user_id="login-user",
        ),
    )
    assert before_login.status_code == 403

    spoofed_email = client.get(
        f"/v2/validation-sharing/runs/{run_id}",
        headers={
            **_auth_headers(
                request_id="req-shared-auto-accept-spoofed-email-001",
                tenant_id="tenant-shared-auto-accept",
                user_id="login-user",
            ),
            "X-User-Email": "login-user@example.com",
        },
    )
    assert spoofed_email.status_code == 403

    after_login = client.get(
        f"/v2/validation-sharing/runs/{run_id}",
        headers=_auth_headers(
            request_id="req-shared-auto-accept-after-login-001",
            tenant_id="tenant-shared-auto-accept",
            user_id="login-user",
            user_email="login-user@example.com",
        ),
    )
    assert after_login.status_code == 200


def test_validation_owner_endpoints_regression_remain_unchanged() -> None:
    client = _client()
    headers = _auth_headers(
        request_id="req-validation-regression-owner-001",
        tenant_id="tenant-validation-regression",
        user_id="owner-validation-regression",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-validation-regression-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    run_get = client.get(
        f"/v2/validation-runs/{run_id}",
        headers={**headers, "X-Request-Id": "req-validation-regression-run-get-001"},
    )
    assert run_get.status_code == 200

    artifact_get = client.get(
        f"/v2/validation-runs/{run_id}/artifact",
        headers={**headers, "X-Request-Id": "req-validation-regression-artifact-001"},
    )
    assert artifact_get.status_code == 200

    review = client.post(
        f"/v2/validation-runs/{run_id}/review",
        headers={
            **headers,
            "X-Request-Id": "req-validation-regression-review-001",
            "Idempotency-Key": "idem-validation-regression-review-001",
        },
        json={
            "reviewerType": "agent",
            "decision": "pass",
            "summary": "Regression flow remains stable.",
            "findings": [],
            "comments": [],
        },
    )
    assert review.status_code == 202

    render = client.post(
        f"/v2/validation-runs/{run_id}/render",
        headers={
            **headers,
            "X-Request-Id": "req-validation-regression-render-001",
            "Idempotency-Key": "idem-validation-regression-render-001",
        },
        json={"format": "html"},
    )
    assert render.status_code == 202
