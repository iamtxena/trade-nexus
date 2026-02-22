"""Runtime contract checks for OpenAPI-backed v2 handlers."""

from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.main import app

HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-runtime-v2-001",
}


def test_openapi_v2_routes_are_registered() -> None:
    expected = {
        ("POST", "/v2/knowledge/search"),
        ("GET", "/v2/knowledge/patterns"),
        ("GET", "/v2/knowledge/regimes/{asset}"),
        ("POST", "/v2/data/exports/backtest"),
        ("GET", "/v2/data/exports/{exportId}"),
        ("POST", "/v2/research/market-scan"),
        ("POST", "/v2/conversations/sessions"),
        ("GET", "/v2/conversations/sessions/{sessionId}"),
        ("POST", "/v2/conversations/sessions/{sessionId}/turns"),
        ("GET", "/v2/validation-runs"),
        ("POST", "/v2/validation-runs"),
        ("GET", "/v2/validation-runs/{runId}"),
        ("GET", "/v2/validation-runs/{runId}/artifact"),
        ("POST", "/v2/validation-runs/{runId}/review"),
        ("POST", "/v2/validation-runs/{runId}/render"),
        ("GET", "/v2/validation-review/runs"),
        ("GET", "/v2/validation-review/runs/{runId}"),
        ("POST", "/v2/validation-review/runs/{runId}/comments"),
        ("POST", "/v2/validation-review/runs/{runId}/decisions"),
        ("POST", "/v2/validation-review/runs/{runId}/renders"),
        ("GET", "/v2/validation-review/runs/{runId}/renders/{format}"),
        ("POST", "/v2/validation-baselines"),
        ("POST", "/v2/validation-regressions/replay"),
        ("POST", "/v2/validation-bots/registrations/invite-code"),
        ("POST", "/v2/validation-bots/registrations/partner-bootstrap"),
        ("POST", "/v2/validation-bots/{botId}/keys/rotate"),
        ("POST", "/v2/validation-bots/{botId}/keys/{keyId}/revoke"),
        ("GET", "/v2/validation-sharing/runs/{runId}/invites"),
        ("POST", "/v2/validation-sharing/runs/{runId}/invites"),
        ("POST", "/v2/validation-sharing/invites/{inviteId}/revoke"),
        ("POST", "/v2/validation-sharing/invites/{inviteId}/accept"),
    }
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.add((method, route.path))
    missing = expected - found
    assert not missing, f"Missing runtime v2 routes: {missing}"


def test_openapi_v2_runtime_status_codes() -> None:
    client = TestClient(app)

    assert (
        client.post(
            "/v2/knowledge/search",
            headers=HEADERS,
            json={"query": "momentum", "assets": ["BTCUSDT"], "limit": 3},
        ).status_code
        == 200
    )
    assert client.get("/v2/knowledge/patterns", headers=HEADERS).status_code == 200
    assert client.get("/v2/knowledge/regimes/BTCUSDT", headers=HEADERS).status_code == 200

    create_export = client.post(
        "/v2/data/exports/backtest",
        headers=HEADERS,
        json={"datasetIds": ["dataset-btc-1h-2025"], "assetClasses": ["crypto"]},
    )
    assert create_export.status_code == 202
    export_id = create_export.json()["export"]["id"]

    assert client.get(f"/v2/data/exports/{export_id}", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/v2/research/market-scan",
            headers=HEADERS,
            json={"assetClasses": ["crypto"], "capital": 25000},
        ).status_code
        == 200
    )

    create_session = client.post(
        "/v2/conversations/sessions",
        headers=HEADERS,
        json={"channel": "openclaw", "topic": "swing-trading"},
    )
    assert create_session.status_code == 201
    session_id = create_session.json()["session"]["id"]

    assert client.get(f"/v2/conversations/sessions/{session_id}", headers=HEADERS).status_code == 200
    assert (
        client.post(
            f"/v2/conversations/sessions/{session_id}/turns",
            headers=HEADERS,
            json={"role": "user", "message": "deploy my strategy after backtest"},
        ).status_code
        == 201
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-run-001"},
        json={
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
        },
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    list_runs = client.get("/v2/validation-runs", headers=HEADERS)
    assert list_runs.status_code == 200
    assert any(item["id"] == run_id for item in list_runs.json().get("runs", []))

    assert client.get(f"/v2/validation-runs/{run_id}", headers=HEADERS).status_code == 200
    assert client.get(f"/v2/validation-runs/{run_id}/artifact", headers=HEADERS).status_code == 200

    assert (
        client.post(
            f"/v2/validation-runs/{run_id}/review",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-review-001"},
            json={
                "reviewerType": "agent",
                "decision": "pass",
                "summary": "Indicator fidelity and metric checks are within policy tolerance.",
                "findings": [],
                "comments": [],
            },
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v2/validation-runs/{run_id}/render",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-render-001"},
            json={"format": "html"},
        ).status_code
        == 202
    )
    review_list = client.get("/v2/validation-review/runs", headers=HEADERS)
    assert review_list.status_code == 200
    assert any(item["id"] == run_id for item in review_list.json().get("items", []))

    assert client.get(f"/v2/validation-review/runs/{run_id}", headers=HEADERS).status_code == 200
    assert (
        client.post(
            f"/v2/validation-review/runs/{run_id}/comments",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-comment-001"},
            json={
                "body": "Review comment from runtime contract check.",
                "evidenceRefs": ["blob://validation/runtime/review-comment.json"],
            },
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v2/validation-review/runs/{run_id}/decisions",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-decision-001"},
            json={
                "action": "approve",
                "decision": "conditional_pass",
                "reason": "Approved with runtime contract safeguards.",
                "evidenceRefs": ["blob://validation/runtime/review-decision.json"],
            },
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v2/validation-review/runs/{run_id}/renders",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-review-render-001"},
            json={"format": "html"},
        ).status_code
        == 202
    )
    assert client.get(f"/v2/validation-review/runs/{run_id}/renders/html", headers=HEADERS).status_code == 200

    create_baseline = client.post(
        "/v2/validation-baselines",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-baseline-001"},
        json={
            "runId": run_id,
            "name": "runtime-v2-validation-baseline",
            "notes": "Contract coverage baseline.",
        },
    )
    assert create_baseline.status_code == 201
    baseline_id = create_baseline.json()["baseline"]["id"]

    assert (
        client.post(
            "/v2/validation-regressions/replay",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-replay-001"},
            json={
                "baselineId": baseline_id,
                "candidateRunId": run_id,
            },
        ).status_code
        == 202
    )

    register_invite_path = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-bot-register-invite-001"},
        json={"inviteCode": "INV-TRIAL-00000001", "botName": "runtime-invite-bot"},
    )
    assert register_invite_path.status_code == 201

    register_partner_path = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-bot-register-partner-001"},
        json={
            "partnerKey": "pk_live_partner_01234567",
            "partnerSecret": "ps_live_partner_89abcdef",
            "ownerEmail": "owner@example.com",
            "botName": "runtime-partner-bot",
        },
    )
    assert register_partner_path.status_code == 201
    partner_bot_id = register_partner_path.json()["bot"]["id"]

    rotate_key = client.post(
        f"/v2/validation-bots/{partner_bot_id}/keys/rotate",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-bot-rotate-001"},
        json={"reason": "runtime contract key rotation"},
    )
    assert rotate_key.status_code == 201
    rotated_key_id = rotate_key.json()["issuedKey"]["key"]["id"]

    assert (
        client.post(
            f"/v2/validation-bots/{partner_bot_id}/keys/{rotated_key_id}/revoke",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-bot-revoke-001"},
            json={"reason": "runtime contract key revoke"},
        ).status_code
        == 200
    )

    create_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-share-create-001"},
        json={"email": "reviewer@example.com", "message": "Please review this run."},
    )
    assert create_invite.status_code == 201
    invite_id = create_invite.json()["invite"]["id"]

    list_invites = client.get(f"/v2/validation-sharing/runs/{run_id}/invites", headers=HEADERS)
    assert list_invites.status_code == 200
    assert any(item["id"] == invite_id for item in list_invites.json().get("items", []))

    assert (
        client.post(
            f"/v2/validation-sharing/invites/{invite_id}/accept",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-share-accept-001"},
            json={"acceptedEmail": "reviewer@example.com"},
        ).status_code
        == 200
    )

    create_revoke_invite = client.post(
        f"/v2/validation-sharing/runs/{run_id}/invites",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-share-create-002"},
        json={"email": "reviewer-two@example.com"},
    )
    assert create_revoke_invite.status_code == 201
    revoke_invite_id = create_revoke_invite.json()["invite"]["id"]

    assert (
        client.post(
            f"/v2/validation-sharing/invites/{revoke_invite_id}/revoke",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-share-revoke-001"},
        ).status_code
        == 200
    )


def test_validation_v2_write_routes_require_idempotency_key_header() -> None:
    client = TestClient(app)

    create_run = client.post(
        "/v2/validation-runs",
        headers=HEADERS,
        json={
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
        },
    )
    assert create_run.status_code == 422

    review = client.post(
        "/v2/validation-runs/valrun-missing/review",
        headers=HEADERS,
        json={
            "reviewerType": "agent",
            "decision": "pass",
            "summary": "Missing idempotency header should fail contract validation.",
            "findings": [],
            "comments": [],
        },
    )
    assert review.status_code == 422

    render = client.post(
        "/v2/validation-runs/valrun-missing/render",
        headers=HEADERS,
        json={"format": "html"},
    )
    assert render.status_code == 422

    review_comment = client.post(
        "/v2/validation-review/runs/valrun-missing/comments",
        headers=HEADERS,
        json={"body": "Missing idempotency key should fail."},
    )
    assert review_comment.status_code == 422

    review_decision = client.post(
        "/v2/validation-review/runs/valrun-missing/decisions",
        headers=HEADERS,
        json={
            "action": "reject",
            "decision": "fail",
            "reason": "Missing idempotency key should fail.",
        },
    )
    assert review_decision.status_code == 422

    review_render = client.post(
        "/v2/validation-review/runs/valrun-missing/renders",
        headers=HEADERS,
        json={"format": "html"},
    )
    assert review_render.status_code == 422

    baseline = client.post(
        "/v2/validation-baselines",
        headers=HEADERS,
        json={"runId": "valrun-missing", "name": "missing"},
    )
    assert baseline.status_code == 422

    replay = client.post(
        "/v2/validation-regressions/replay",
        headers=HEADERS,
        json={
            "baselineId": "valbase-missing",
            "candidateRunId": "valrun-missing",
        },
    )
    assert replay.status_code == 422

    register_invite = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers=HEADERS,
        json={"inviteCode": "INV-TRIAL-00000001", "botName": "missing"},
    )
    assert register_invite.status_code == 422

    register_partner = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers=HEADERS,
        json={
            "partnerKey": "pk_live_partner_01234567",
            "partnerSecret": "ps_live_partner_89abcdef",
            "ownerEmail": "owner@example.com",
            "botName": "missing",
        },
    )
    assert register_partner.status_code == 422

    rotate_bot_key = client.post(
        "/v2/validation-bots/bot-missing/keys/rotate",
        headers=HEADERS,
        json={"reason": "missing idempotency key"},
    )
    assert rotate_bot_key.status_code == 422

    revoke_bot_key = client.post(
        "/v2/validation-bots/bot-missing/keys/botkey-missing/revoke",
        headers=HEADERS,
        json={"reason": "missing idempotency key"},
    )
    assert revoke_bot_key.status_code == 422

    create_share_invite = client.post(
        "/v2/validation-sharing/runs/valrun-missing/invites",
        headers=HEADERS,
        json={"email": "reviewer@example.com"},
    )
    assert create_share_invite.status_code == 422

    revoke_share_invite = client.post(
        "/v2/validation-sharing/invites/vinvite-missing/revoke",
        headers=HEADERS,
    )
    assert revoke_share_invite.status_code == 422

    accept_share_invite = client.post(
        "/v2/validation-sharing/invites/vinvite-missing/accept",
        headers=HEADERS,
        json={"acceptedEmail": "reviewer@example.com"},
    )
    assert accept_share_invite.status_code == 422


def test_validation_bot_registration_routes_allow_unauthenticated_access() -> None:
    client = TestClient(app)
    public_headers = {"X-Request-Id": "req-runtime-v2-public-registration-001"}

    invite_registration = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers={**public_headers, "Idempotency-Key": "idem-runtime-v2-public-register-invite-001"},
        json={"inviteCode": "INV-TRIAL-00000011", "botName": "runtime-public-invite-bot"},
    )
    assert invite_registration.status_code == 201
    assert invite_registration.json()["bot"]["registrationPath"] == "invite_code_trial"

    partner_registration = client.post(
        "/v2/validation-bots/registrations/partner-bootstrap",
        headers={**public_headers, "Idempotency-Key": "idem-runtime-v2-public-register-partner-001"},
        json={
            "partnerKey": "pk_live_partner_11223344",
            "partnerSecret": "ps_live_partner_aabbccdd",
            "ownerEmail": "public-owner@example.com",
            "botName": "runtime-public-partner-bot",
        },
    )
    assert partner_registration.status_code == 201
    assert partner_registration.json()["bot"]["registrationPath"] == "partner_bootstrap"

    invite_registration_with_invalid_auth = client.post(
        "/v2/validation-bots/registrations/invite-code",
        headers={
            **public_headers,
            "Idempotency-Key": "idem-runtime-v2-public-register-invite-002",
            "Authorization": "Bearer invalid-token",
        },
        json={"inviteCode": "INV-TRIAL-00000012", "botName": "runtime-public-invite-bot-invalid-auth"},
    )
    assert invite_registration_with_invalid_auth.status_code == 201

    protected_write = client.post(
        "/v2/validation-sharing/runs/valrun-public-test/invites",
        headers={**public_headers, "Idempotency-Key": "idem-runtime-v2-public-protected-write-001"},
        json={"email": "reviewer@example.com"},
    )
    assert protected_write.status_code == 401
