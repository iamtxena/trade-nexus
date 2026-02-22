"""Runtime contract checks for /v2/validation-review endpoints (#276)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient

from src.main import app

_JWT_SECRET = os.environ.setdefault("PLATFORM_AUTH_JWT_HS256_SECRET", "test-validation-review-secret")


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


def _validation_headers(
    *,
    request_id: str,
    tenant_id: str,
    user_id: str,
) -> dict[str, str]:
    token = _jwt_token({"sub": user_id, "tenant_id": tenant_id})
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "test-key",
        "X-Request-Id": request_id,
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
    }


def _create_validation_run(
    client: TestClient,
    *,
    headers: dict[str, str],
    idempotency_key: str,
) -> str:
    response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
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
                "requireTraderReview": True,
                "hardFailOnMissingIndicators": True,
                "failClosedOnEvidenceUnavailable": True,
            },
        },
    )
    assert response.status_code == 202
    return response.json()["run"]["id"]


def _assert_error_envelope(payload: dict[str, object]) -> None:
    assert "requestId" in payload
    assert "error" in payload
    error = payload["error"]
    assert isinstance(error, dict)
    assert "code" in error
    assert "message" in error


def test_validation_review_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get(
        "/v2/validation-review/runs",
        headers={"X-Request-Id": "req-v2-validation-review-unauth-001"},
    )
    assert response.status_code == 401
    payload = response.json()
    _assert_error_envelope(payload)
    assert payload["requestId"] == "req-v2-validation-review-unauth-001"
    assert payload["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_validation_review_list_and_detail_are_tenant_scoped() -> None:
    client = TestClient(app)
    scoped_headers = _validation_headers(
        request_id="req-v2-validation-review-tenant-001",
        tenant_id="tenant-v2-validation-review-scope",
        user_id="user-v2-validation-review-scope",
    )
    other_headers = _validation_headers(
        request_id="req-v2-validation-review-tenant-002",
        tenant_id="tenant-v2-validation-review-other",
        user_id="user-v2-validation-review-other",
    )

    scoped_run = _create_validation_run(
        client,
        headers=scoped_headers,
        idempotency_key="idem-v2-validation-review-tenant-run-001",
    )
    other_run = _create_validation_run(
        client,
        headers=other_headers,
        idempotency_key="idem-v2-validation-review-tenant-run-002",
    )

    scoped_list = client.get("/v2/validation-review/runs", headers=scoped_headers)
    assert scoped_list.status_code == 200
    listed_ids = {item["id"] for item in scoped_list.json()["items"]}
    assert scoped_run in listed_ids
    assert other_run not in listed_ids

    forbidden_detail = client.get(f"/v2/validation-review/runs/{other_run}", headers=scoped_headers)
    assert forbidden_detail.status_code == 404
    forbidden_payload = forbidden_detail.json()
    _assert_error_envelope(forbidden_payload)
    assert forbidden_payload["error"]["code"] == "VALIDATION_RUN_NOT_FOUND"


def test_validation_review_write_routes_are_idempotent() -> None:
    client = TestClient(app)
    headers = _validation_headers(
        request_id="req-v2-validation-review-idem-001",
        tenant_id="tenant-v2-validation-review-idem",
        user_id="user-v2-validation-review-idem",
    )
    run_id = _create_validation_run(
        client,
        headers=headers,
        idempotency_key="idem-v2-validation-review-idem-run-001",
    )

    comment_payload = {
        "body": "Comment from review idempotency contract test.",
        "evidenceRefs": ["blob://validation/review/comment-001.json"],
    }
    comment_headers = {**headers, "Idempotency-Key": "idem-v2-validation-review-comment-001"}
    first_comment = client.post(
        f"/v2/validation-review/runs/{run_id}/comments",
        headers=comment_headers,
        json=comment_payload,
    )
    assert first_comment.status_code == 202
    second_comment = client.post(
        f"/v2/validation-review/runs/{run_id}/comments",
        headers=comment_headers,
        json=comment_payload,
    )
    assert second_comment.status_code == 202
    assert second_comment.json()["comment"]["id"] == first_comment.json()["comment"]["id"]
    comment_conflict = client.post(
        f"/v2/validation-review/runs/{run_id}/comments",
        headers=comment_headers,
        json={**comment_payload, "body": "different"},
    )
    assert comment_conflict.status_code == 409
    assert comment_conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    decision_payload = {
        "action": "approve",
        "decision": "conditional_pass",
        "reason": "Approve with safeguards.",
        "evidenceRefs": ["blob://validation/review/decision-001.json"],
    }
    decision_headers = {**headers, "Idempotency-Key": "idem-v2-validation-review-decision-001"}
    first_decision = client.post(
        f"/v2/validation-review/runs/{run_id}/decisions",
        headers=decision_headers,
        json=decision_payload,
    )
    assert first_decision.status_code == 202
    second_decision = client.post(
        f"/v2/validation-review/runs/{run_id}/decisions",
        headers=decision_headers,
        json=decision_payload,
    )
    assert second_decision.status_code == 202
    assert second_decision.json()["decision"]["createdAt"] == first_decision.json()["decision"]["createdAt"]
    decision_conflict = client.post(
        f"/v2/validation-review/runs/{run_id}/decisions",
        headers=decision_headers,
        json={
            "action": "reject",
            "decision": "fail",
            "reason": "different payload",
            "evidenceRefs": ["blob://validation/review/decision-002.json"],
        },
    )
    assert decision_conflict.status_code == 409
    assert decision_conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    render_headers = {**headers, "Idempotency-Key": "idem-v2-validation-review-render-001"}
    first_render = client.post(
        f"/v2/validation-review/runs/{run_id}/renders",
        headers=render_headers,
        json={"format": "html"},
    )
    assert first_render.status_code == 202
    second_render = client.post(
        f"/v2/validation-review/runs/{run_id}/renders",
        headers=render_headers,
        json={"format": "html"},
    )
    assert second_render.status_code == 202
    assert second_render.json()["render"]["requestedAt"] == first_render.json()["render"]["requestedAt"]
    render_conflict = client.post(
        f"/v2/validation-review/runs/{run_id}/renders",
        headers=render_headers,
        json={"format": "pdf"},
    )
    assert render_conflict.status_code == 409
    assert render_conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_validation_review_routes_return_error_envelopes() -> None:
    client = TestClient(app)
    headers = _validation_headers(
        request_id="req-v2-validation-review-errors-001",
        tenant_id="tenant-v2-validation-review-errors",
        user_id="user-v2-validation-review-errors",
    )
    run_id = _create_validation_run(
        client,
        headers=headers,
        idempotency_key="idem-v2-validation-review-errors-run-001",
    )

    missing_run = client.post(
        "/v2/validation-review/runs/valrun-missing/comments",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-review-errors-missing-001"},
        json={
            "body": "attempting to comment on missing run",
            "evidenceRefs": ["blob://validation/review/missing.json"],
        },
    )
    assert missing_run.status_code == 404
    missing_payload = missing_run.json()
    _assert_error_envelope(missing_payload)
    assert missing_payload["error"]["code"] == "VALIDATION_RUN_NOT_FOUND"

    invalid_decision = client.post(
        f"/v2/validation-review/runs/{run_id}/decisions",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-review-errors-invalid-001"},
        json={
            "action": "approve",
            "decision": "fail",
            "reason": "invalid action/decision pair",
            "evidenceRefs": ["blob://validation/review/invalid-decision.json"],
        },
    )
    assert invalid_decision.status_code == 400
    invalid_payload = invalid_decision.json()
    _assert_error_envelope(invalid_payload)
    assert invalid_payload["error"]["code"] == "VALIDATION_REVIEW_INVALID"

    missing_render = client.get(f"/v2/validation-review/runs/{run_id}/renders/html", headers=headers)
    assert missing_render.status_code == 404
    render_payload = missing_render.json()
    _assert_error_envelope(render_payload)
    assert render_payload["error"]["code"] == "VALIDATION_RENDER_NOT_FOUND"
