"""Runtime tests for validation identity linkage and shared-run access controls."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
        identity._pending_share_invite_index.clear()  # noqa: SLF001
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
            "validation_run_invites",
            "validation_invite_revocations",
            "validation_invite_acceptance",
            "validation_bot_registrations_invite_code",
            "validation_bot_registrations_partner_bootstrap",
            "validation_bot_key_rotations",
            "validation_bot_key_revocations",
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


def test_runtime_bot_partner_registration_public_path_derives_owner_identity() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001

    owner_email = "public-owner@example.com"
    digest = hashlib.sha256(owner_email.encode("utf-8")).hexdigest()
    derived_user_id = f"user-email-{digest[:12]}"
    derived_tenant_id = f"tenant-email-{digest[12:24]}"

    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={
            "X-Request-Id": "req-runtime-bot-public-partner-register-001",
            "Idempotency-Key": "idem-runtime-bot-public-partner-register-001",
        },
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": owner_email,
            "botName": "Public Runtime Bot",
        },
    )
    assert register.status_code == 201
    assert register.json()["bot"]["ownerUserId"] == derived_user_id
    assert register.json()["bot"]["tenantId"] == derived_tenant_id
    runtime_key = register.json()["issuedKey"]["rawKey"]

    derived_owner_headers = _auth_headers(
        request_id="req-runtime-bot-public-derived-owner-001",
        tenant_id=derived_tenant_id,
        user_id=derived_user_id,
        user_email=owner_email,
    )
    create_run = client.post(
        "/v2/validation-runs",
        headers={
            **derived_owner_headers,
            "X-Request-Id": "req-runtime-bot-public-derived-run-001",
            "X-API-Key": runtime_key,
            "Idempotency-Key": "idem-runtime-bot-public-derived-run-001",
        },
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    assert create_run.json()["run"]["actor"]["actorType"] == "bot"
    assert create_run.json()["run"]["actor"]["actorId"] == "public-runtime-bot"


def test_runtime_bot_api_key_only_auth_sets_runtime_tenant_context() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001

    owner_headers = _auth_headers(
        request_id="req-runtime-bot-api-key-only-owner-register-001",
        tenant_id="tenant-runtime-bot-only-key",
        user_id="owner-runtime-bot-only-key",
    )
    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-runtime-bot-api-key-only-register-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot-only-key@example.com",
            "botName": "Runtime Bot API Key Only",
        },
    )
    assert register.status_code == 201
    runtime_key = register.json()["issuedKey"]["rawKey"]

    create_run = client.post(
        "/v2/validation-runs",
        headers={
            "X-Request-Id": "req-runtime-bot-api-key-only-run-001",
            "X-API-Key": runtime_key,
            "Idempotency-Key": "idem-runtime-bot-api-key-only-run-001",
        },
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]
    assert create_run.json()["run"]["actor"]["actorType"] == "bot"
    assert create_run.json()["run"]["actor"]["actorId"] == "runtime-bot-api-key-only"

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_run(  # noqa: SLF001
            run_id=run_id,
            tenant_id="tenant-runtime-bot-only-key",
            user_id="owner-runtime-bot-only-key",
        )
    )
    assert persisted is not None
    assert persisted.metadata.owner_user_id == "owner-runtime-bot-only-key"
    assert persisted.metadata.actor_type == "bot"
    assert persisted.metadata.actor_id == "runtime-bot-api-key-only"


def test_runtime_bot_revoked_key_with_wrong_secret_returns_invalid_not_revoked() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001
    owner_headers = _auth_headers(
        request_id="req-runtime-bot-revoked-oracle-owner-001",
        tenant_id="tenant-runtime-bot-revoked-oracle",
        user_id="owner-runtime-bot-revoked-oracle",
    )

    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-runtime-bot-revoked-oracle-register-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot-revoked-oracle@example.com",
            "botName": "Runtime Bot Revoked Oracle",
        },
    )
    assert register.status_code == 201
    runtime_key = register.json()["issuedKey"]["rawKey"]
    key_id = register.json()["issuedKey"]["key"]["id"]

    revoke = client.post(
        f"/v2/validation-bots/runtime-bot-revoked-oracle/keys/{key_id}/revoke",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-revoked-oracle-revoke-001",
            "Idempotency-Key": "idem-runtime-bot-revoked-oracle-revoke-001",
        },
        json={},
    )
    assert revoke.status_code == 200

    wrong_secret_key = ".".join([*runtime_key.split(".")[:-1], "nottherealsecret"])
    invalid = client.post(
        "/v2/validation-runs",
        headers={
            "X-Request-Id": "req-runtime-bot-revoked-oracle-invalid-001",
            "X-API-Key": wrong_secret_key,
            "Idempotency-Key": "idem-runtime-bot-revoked-oracle-invalid-001",
        },
        json=_validation_run_payload(),
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "BOT_API_KEY_INVALID"

    revoked = client.post(
        "/v2/validation-runs",
        headers={
            "X-Request-Id": "req-runtime-bot-revoked-oracle-revoked-001",
            "X-API-Key": runtime_key,
            "Idempotency-Key": "idem-runtime-bot-revoked-oracle-revoked-001",
        },
        json=_validation_run_payload(),
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "BOT_API_KEY_REVOKED"


def test_runtime_bot_partner_registration_is_idempotent_for_retries() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001
    owner_headers = _auth_headers(
        request_id="req-runtime-bot-partner-idempotent-register-001",
        tenant_id="tenant-runtime-bot-partner-idempotent",
        user_id="owner-runtime-bot-partner-idempotent",
    )
    payload = {
        "partnerKey": "partner-bootstrap",
        "partnerSecret": "partner-secret",
        "ownerEmail": "owner-runtime-bot-partner-idempotent@example.com",
        "botName": "Runtime Bot Partner Idempotent",
    }

    first = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-runtime-bot-partner-idempotent-register-001"},
        json=payload,
    )
    assert first.status_code == 201

    replay = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-partner-idempotent-register-002",
            "Idempotency-Key": "idem-runtime-bot-partner-idempotent-register-001",
        },
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.json() == first.json()

    issued_key = first.json()["issuedKey"]["key"]["id"]
    indexed = router_v2_module._identity_service._bot_key_index[  # noqa: SLF001
        (
            "tenant-runtime-bot-partner-idempotent",
            "owner-runtime-bot-partner-idempotent",
            "runtime-bot-partner-idempotent",
        )
    ]
    assert sorted(indexed) == [issued_key]
    issued_record = router_v2_module._identity_service.get_bot_key(key_id=issued_key)
    assert issued_record is not None
    assert not issued_record.revoked

    register_events = [
        item
        for item in router_v1_module._store.validation_identity_audit_events
        if item.event_type == "register" and item.metadata.get("botId") == "runtime-bot-partner-idempotent"
    ]
    assert len(register_events) == 1


def test_runtime_bot_key_rotation_is_idempotent_for_retries() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001
    owner_headers = _auth_headers(
        request_id="req-runtime-bot-rotate-idempotent-register-001",
        tenant_id="tenant-runtime-bot-rotate-idempotent",
        user_id="owner-runtime-bot-rotate-idempotent",
    )

    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-runtime-bot-rotate-idempotent-register-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot-rotate-idempotent@example.com",
            "botName": "Runtime Bot Rotate Idempotent",
        },
    )
    assert register.status_code == 201

    first_rotate = client.post(
        "/v2/validation-bots/runtime-bot-rotate-idempotent/keys/rotate",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-rotate-idempotent-001",
            "Idempotency-Key": "idem-runtime-bot-rotate-idempotent-001",
        },
        json={},
    )
    assert first_rotate.status_code == 201

    replay_rotate = client.post(
        "/v2/validation-bots/runtime-bot-rotate-idempotent/keys/rotate",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-rotate-idempotent-002",
            "Idempotency-Key": "idem-runtime-bot-rotate-idempotent-001",
        },
        json={},
    )
    assert replay_rotate.status_code == 201
    assert replay_rotate.json() == first_rotate.json()

    active_key_id = first_rotate.json()["issuedKey"]["key"]["id"]
    active_record = router_v2_module._identity_service.get_bot_key(key_id=active_key_id)
    assert active_record is not None
    assert not active_record.revoked

    bot_keys = [
        item
        for item in router_v2_module._identity_service._bot_keys.values()  # noqa: SLF001
        if item.bot_id == "runtime-bot-rotate-idempotent"
    ]
    assert len(bot_keys) == 2
    assert sum(1 for item in bot_keys if item.revoked_at is None) == 1

    rotate_events = [
        item
        for item in router_v1_module._store.validation_identity_audit_events
        if item.event_type == "rotate" and item.metadata.get("botId") == "runtime-bot-rotate-idempotent"
    ]
    assert len(rotate_events) == 1


def test_runtime_bot_key_rotation_and_revoke_normalize_response_bot_id_and_key_lookup() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001
    owner_headers = _auth_headers(
        request_id="req-runtime-bot-normalize-register-001",
        tenant_id="tenant-runtime-bot-normalize",
        user_id="owner-runtime-bot-normalize",
    )

    register = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-runtime-bot-normalize-register-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-runtime-bot-normalize@example.com",
            "botName": "Runtime Bot Normalize",
        },
    )
    assert register.status_code == 201

    rotate = client.post(
        "/v2/validation-bots/RUNTIME-BOT-NORMALIZE/keys/rotate",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-normalize-rotate-001",
            "Idempotency-Key": "idem-runtime-bot-normalize-rotate-001",
        },
        json={},
    )
    assert rotate.status_code == 201
    assert rotate.json()["botId"] == "runtime-bot-normalize"
    assert rotate.json()["issuedKey"]["key"]["botId"] == "runtime-bot-normalize"
    key_id = rotate.json()["issuedKey"]["key"]["id"]

    revoke = client.post(
        f"/v2/validation-bots/RUNTIME-BOT-NORMALIZE/keys/{key_id}%20/revoke",
        headers={
            **owner_headers,
            "X-Request-Id": "req-runtime-bot-normalize-revoke-001",
            "Idempotency-Key": "idem-runtime-bot-normalize-revoke-001",
        },
        json={},
    )
    assert revoke.status_code == 200
    assert revoke.json()["botId"] == "runtime-bot-normalize"
    assert revoke.json()["key"]["id"] == key_id
    assert revoke.json()["key"]["botId"] == "runtime-bot-normalize"
    assert revoke.json()["key"]["status"] == "revoked"


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


def test_non_validation_routes_ignore_validation_bot_api_key_header() -> None:
    client = _client()
    response = client.get(
        "/v2/conversations/sessions/session-does-not-exist",
        headers={
            "X-Request-Id": "req-non-validation-bot-api-key-001",
            "X-Tenant-Id": "tenant-non-validation-bot-api-key",
            "X-User-Id": "user-non-validation-bot-api-key",
            "X-API-Key": "tnx.bot.invalid",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_SESSION_NOT_FOUND"


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


def test_shared_validation_invite_rejects_duplicate_pending_email() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-conflict-owner-001",
        tenant_id="tenant-shared-validation-conflict",
        user_id="owner-shared-validation-conflict",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-conflict-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    first = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-conflict-share-001",
            "Idempotency-Key": "idem-shared-validation-conflict-share-001",
        },
        json={"email": "duplicate@example.com"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-conflict-share-002",
            "Idempotency-Key": "idem-shared-validation-conflict-share-002",
        },
        json={"email": "duplicate@example.com"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "VALIDATION_INVITE_CONFLICT"

    invites = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-conflict-list-001"},
    )
    assert invites.status_code == 200
    assert len(invites.json()["items"]) == 1


def test_shared_validation_invite_endpoints_honor_idempotency_keys() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-idempotency-owner-001",
        tenant_id="tenant-shared-validation-idempotency",
        user_id="owner-shared-validation-idempotency",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-idempotency-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    first_create = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-create-001",
            "Idempotency-Key": "idem-shared-validation-idempotency-create-001",
        },
        json={"email": "idempotent-create@example.com"},
    )
    assert first_create.status_code == 201

    replay_create = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-create-002",
            "Idempotency-Key": "idem-shared-validation-idempotency-create-001",
        },
        json={"email": "idempotent-create@example.com"},
    )
    assert replay_create.status_code == 201
    assert replay_create.json() == first_create.json()

    conflict_create = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-create-003",
            "Idempotency-Key": "idem-shared-validation-idempotency-create-001",
        },
        json={"email": "idempotent-create-different@example.com"},
    )
    assert conflict_create.status_code == 409
    assert conflict_create.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    invite_id = first_create.json()["invite"]["id"]
    first_revoke = client.post(
        f"/v2/validation-sharing/invites/{invite_id}/revoke",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-revoke-001",
            "Idempotency-Key": "idem-shared-validation-idempotency-revoke-001",
        },
        json={},
    )
    assert first_revoke.status_code == 200

    replay_revoke = client.post(
        f"/v2/validation-sharing/invites/{invite_id}/revoke",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-revoke-002",
            "Idempotency-Key": "idem-shared-validation-idempotency-revoke-001",
        },
        json={},
    )
    assert replay_revoke.status_code == 200
    assert replay_revoke.json() == first_revoke.json()

    create_for_accept = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-idempotency-create-accept-001",
            "Idempotency-Key": "idem-shared-validation-idempotency-create-accept-001",
        },
        json={"email": "idempotent-accept@example.com"},
    )
    assert create_for_accept.status_code == 201
    invite_for_accept = create_for_accept.json()["invite"]["id"]

    accept_headers = _auth_headers(
        request_id="req-shared-validation-idempotency-accept-user-001",
        tenant_id="tenant-shared-validation-idempotency",
        user_id="idempotent-accept-user",
        user_email="idempotent-accept@example.com",
    )
    first_accept = client.post(
        f"/v2/validation-sharing/invites/{invite_for_accept}/accept",
        headers={**accept_headers, "Idempotency-Key": "idem-shared-validation-idempotency-accept-001"},
        json={"acceptedEmail": "idempotent-accept@example.com"},
    )
    assert first_accept.status_code == 200

    replay_accept = client.post(
        f"/v2/validation-sharing/invites/{invite_for_accept}/accept",
        headers={
            **accept_headers,
            "X-Request-Id": "req-shared-validation-idempotency-accept-user-002",
            "Idempotency-Key": "idem-shared-validation-idempotency-accept-001",
        },
        json={"acceptedEmail": "idempotent-accept@example.com"},
    )
    assert replay_accept.status_code == 200
    assert replay_accept.json() == first_accept.json()

    conflict_accept = client.post(
        f"/v2/validation-sharing/invites/{invite_for_accept}/accept",
        headers={
            **accept_headers,
            "X-Request-Id": "req-shared-validation-idempotency-accept-user-003",
            "Idempotency-Key": "idem-shared-validation-idempotency-accept-001",
        },
        json={"acceptedEmail": "other@example.com"},
    )
    assert conflict_accept.status_code == 409
    assert conflict_accept.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_shared_validation_expired_pending_invite_allows_new_invite_creation() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-expired-duplicate-owner-001",
        tenant_id="tenant-shared-validation-expired-duplicate",
        user_id="owner-shared-validation-expired-duplicate",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-expired-duplicate-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    first = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expired-duplicate-share-001",
            "Idempotency-Key": "idem-shared-validation-expired-duplicate-share-001",
        },
        json={"email": "stale-invite@example.com"},
    )
    assert first.status_code == 201
    first_invite_id = first.json()["invite"]["id"]

    invites = router_v2_module._identity_service._share_invites_by_run[run_id]  # noqa: SLF001
    invites[0] = replace(
        invites[0],
        status="pending",
        expires_at=(datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )

    second = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expired-duplicate-share-002",
            "Idempotency-Key": "idem-shared-validation-expired-duplicate-share-002",
        },
        json={"email": "stale-invite@example.com"},
    )
    assert second.status_code == 201
    assert second.json()["invite"]["id"] != first_invite_id

    listed = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-expired-duplicate-list-001"},
    )
    assert listed.status_code == 200
    status_by_id = {item["id"]: item["status"] for item in listed.json()["items"]}
    assert status_by_id[first_invite_id] == "expired"
    assert status_by_id[second.json()["invite"]["id"]] == "pending"


def test_shared_validation_invite_list_supports_cursor_pagination() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-pagination-owner-001",
        tenant_id="tenant-shared-validation-pagination",
        user_id="owner-shared-validation-pagination",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-pagination-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    first_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-pagination-share-001",
            "Idempotency-Key": "idem-shared-validation-pagination-share-001",
        },
        json={"email": "page-one@example.com"},
    )
    assert first_invite.status_code == 201

    second_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-pagination-share-002",
            "Idempotency-Key": "idem-shared-validation-pagination-share-002",
        },
        json={"email": "page-two@example.com"},
    )
    assert second_invite.status_code == 201

    page_one = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        params={"limit": 1},
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-pagination-list-001"},
    )
    assert page_one.status_code == 200
    assert len(page_one.json()["items"]) == 1
    assert page_one.json()["items"][0]["email"] == "page-one@example.com"
    assert page_one.json()["nextCursor"] == "1"

    page_two = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        params={"limit": 1, "cursor": page_one.json()["nextCursor"]},
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-pagination-list-002"},
    )
    assert page_two.status_code == 200
    assert len(page_two.json()["items"]) == 1
    assert page_two.json()["items"][0]["email"] == "page-two@example.com"
    assert page_two.json()["nextCursor"] is None

    invalid_cursor = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        params={"limit": 1, "cursor": "invalid"},
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-pagination-list-003"},
    )
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["error"]["code"] == "VALIDATION_SHARE_INVALID"


def test_shared_validation_invite_expiration_defaults_and_validation() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-expiry-owner-001",
        tenant_id="tenant-shared-validation-expiry",
        user_id="owner-shared-validation-expiry",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-expiry-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    default_expiry_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expiry-share-default-001",
            "Idempotency-Key": "idem-shared-validation-expiry-share-default-001",
        },
        json={"email": "default-expiry@example.com"},
    )
    assert default_expiry_invite.status_code == 201
    expires_at = default_expiry_invite.json()["invite"]["expiresAt"]
    assert isinstance(expires_at, str)
    expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    now = datetime.now(tz=UTC)
    assert expires_at_dt > now + timedelta(days=6)
    assert expires_at_dt < now + timedelta(days=8)

    invalid_expiry = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expiry-share-invalid-001",
            "Idempotency-Key": "idem-shared-validation-expiry-share-invalid-001",
        },
        json={"email": "invalid-expiry@example.com", "expiresAt": "not-a-timestamp"},
    )
    assert invalid_expiry.status_code == 400
    assert invalid_expiry.json()["error"]["code"] == "VALIDATION_SHARE_INVALID"

    past_expiry = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expiry-share-past-001",
            "Idempotency-Key": "idem-shared-validation-expiry-share-past-001",
        },
        json={
            "email": "past-expiry@example.com",
            "expiresAt": (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        },
    )
    assert past_expiry.status_code == 400
    assert past_expiry.json()["error"]["code"] == "VALIDATION_SHARE_INVALID"


def test_shared_validation_invite_list_surfaces_expired_status() -> None:
    client = _client()
    owner_headers = _auth_headers(
        request_id="req-shared-validation-expired-status-owner-001",
        tenant_id="tenant-shared-validation-expired-status",
        user_id="owner-shared-validation-expired-status",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-validation-expired-status-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    create_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-validation-expired-status-share-001",
            "Idempotency-Key": "idem-shared-validation-expired-status-share-001",
        },
        json={"email": "expired-status@example.com"},
    )
    assert create_invite.status_code == 201
    invite_id = create_invite.json()["invite"]["id"]

    invites = router_v2_module._identity_service._share_invites_by_run[run_id]  # noqa: SLF001
    invites[0] = replace(
        invites[0],
        status="pending",
        expires_at=(datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )

    listed = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**owner_headers, "X-Request-Id": "req-shared-validation-expired-status-list-001"},
    )
    assert listed.status_code == 200
    invite = next(item for item in listed.json()["items"] if item["id"] == invite_id)
    assert invite["status"] == "expired"


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


def test_shared_invite_accept_rejects_mixed_jwt_and_bot_key_identity() -> None:
    client = _client()
    router_v2_module._identity_service._partner_credentials = {"partner-bootstrap": "partner-secret"}  # noqa: SLF001
    owner_headers = _auth_headers(
        request_id="req-shared-invite-mixed-owner-001",
        tenant_id="tenant-shared-invite-mixed",
        user_id="owner-shared-invite-mixed",
    )

    register_bot = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-invite-mixed-register-bot-001"},
        json={
            "partnerKey": "partner-bootstrap",
            "partnerSecret": "partner-secret",
            "ownerEmail": "owner-shared-invite-mixed@example.com",
            "botName": "Shared Invite Mix Bot",
        },
    )
    assert register_bot.status_code == 201
    runtime_key = register_bot.json()["issuedKey"]["rawKey"]

    create_run = client.post(
        "/v2/validation-runs",
        headers={**owner_headers, "Idempotency-Key": "idem-shared-invite-mixed-run-001"},
        json=_validation_run_payload(),
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={
            **owner_headers,
            "X-Request-Id": "req-shared-invite-mixed-share-001",
            "Idempotency-Key": "idem-shared-invite-mixed-share-001",
        },
        json={"email": "invitee-mixed@example.com"},
    )
    assert invite.status_code == 201
    invite_id = invite.json()["invite"]["id"]

    mixed_accept = client.post(
        f"/v2/validation-sharing/invites/{invite_id}/accept",
        headers={
            **_auth_headers(
                request_id="req-shared-invite-mixed-accept-001",
                tenant_id="tenant-shared-invite-mixed",
                user_id="invitee-user-mixed",
                user_email="invitee-mixed@example.com",
            ),
            "X-API-Key": runtime_key,
            "Idempotency-Key": "idem-shared-invite-mixed-accept-001",
        },
        json={"acceptedEmail": "invitee-mixed@example.com"},
    )
    assert mixed_accept.status_code == 403
    assert mixed_accept.json()["error"]["code"] == "VALIDATION_INVITE_EMAIL_MISMATCH"

    listed = client.get(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**owner_headers, "X-Request-Id": "req-shared-invite-mixed-list-001"},
    )
    assert listed.status_code == 200
    invite_item = next(item for item in listed.json()["items"] if item["id"] == invite_id)
    assert invite_item["status"] == "pending"


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
