"""Contract-oriented smoke tests for Platform API v2 handlers."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.platform_api import router_v1 as router_v1_module
from src.platform_api import router_v2 as router_v2_module

HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "tnx.bot.runtime-contract-001.secret-001",
    "X-Request-Id": "req-v2-contract-001",
}

_JWT_SECRET = os.environ.setdefault("PLATFORM_AUTH_JWT_HS256_SECRET", "test-platform-v2-secret")


def _client() -> TestClient:
    return TestClient(app)


def _jwt_segment(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _jwt_token(payload: dict[str, object]) -> str:
    claims_payload = dict(payload)
    claims_payload.setdefault("exp", int(time.time()) + 300)
    header = _jwt_segment({"alg": "HS256", "typ": "JWT"})
    claims = _jwt_segment(claims_payload)
    signing_input = f"{header}.{claims}".encode("utf-8")
    signature = hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{header}.{claims}.{encoded_signature}"


def _validation_headers(
    *,
    request_id: str,
    tenant_id: str,
    user_id: str,
    include_identity_headers: bool = True,
    spoof_tenant_id: str | None = None,
    spoof_user_id: str | None = None,
) -> dict[str, str]:
    token = _jwt_token({"sub": user_id, "tenant_id": tenant_id})
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": HEADERS["X-API-Key"],
        "X-Request-Id": request_id,
    }
    if include_identity_headers:
        headers["X-Tenant-Id"] = spoof_tenant_id if spoof_tenant_id is not None else tenant_id
        headers["X-User-Id"] = spoof_user_id if spoof_user_id is not None else user_id
    return headers


@pytest.fixture(autouse=True)
def _restore_ml_signal_snapshots() -> None:
    original = copy.deepcopy(router_v1_module._store.ml_signal_snapshots)
    yield
    router_v1_module._store.ml_signal_snapshots = original


def test_knowledge_v2_routes() -> None:
    client = _client()

    search_resp = client.post(
        "/v2/knowledge/search",
        headers=HEADERS,
        json={"query": "reversion", "assets": ["BTCUSDT"], "limit": 5},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["requestId"] == HEADERS["X-Request-Id"]

    list_resp = client.get("/v2/knowledge/patterns", headers=HEADERS)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1

    regime_resp = client.get("/v2/knowledge/regimes/BTCUSDT", headers=HEADERS)
    assert regime_resp.status_code == 200
    assert regime_resp.json()["regime"]["asset"] == "BTCUSDT"


def test_data_export_v2_routes() -> None:
    client = _client()

    create_resp = client.post(
        "/v2/data/exports/backtest",
        headers=HEADERS,
        json={"datasetIds": ["dataset-btc-1h-2025"], "assetClasses": ["crypto"]},
    )
    assert create_resp.status_code == 202
    export_id = create_resp.json()["export"]["id"]

    get_resp = client.get(f"/v2/data/exports/{export_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["export"]["id"] == export_id


def test_research_v2_route_includes_knowledge_and_context() -> None:
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "knowledgeEvidence" in payload
    assert "dataContextSummary" in payload
    assert payload["requestId"] == HEADERS["X-Request-Id"]


def test_research_v2_route_returns_provider_budget_exceeded_error() -> None:
    client = _client()
    original_budget = copy.deepcopy(router_v1_module._store.research_provider_budget)
    original_events = copy.deepcopy(router_v1_module._store.research_budget_events)
    try:
        router_v1_module._store.research_provider_budget = {
            "maxTotalCostUsd": 1.0,
            "maxPerRequestCostUsd": 0.1,
            "estimatedMarketScanCostUsd": 0.2,
            "spentCostUsd": 0.0,
        }
        response = client.post(
            "/v2/research/market-scan",
            headers=HEADERS,
            json={"assetClasses": ["crypto"], "capital": 25000},
        )
    finally:
        router_v1_module._store.research_provider_budget = original_budget
        router_v1_module._store.research_budget_events = original_events

    assert response.status_code == 429
    payload = response.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert payload["error"]["code"] == "RESEARCH_PROVIDER_BUDGET_EXCEEDED"


def test_research_v2_route_applies_ml_signal_scoring(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Uptrend with stable liquidity.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "mlSignals": {
                "prediction": {"direction": "bullish", "confidence": 0.8, "timeframe": "24h"},
                "sentiment": {"score": 0.7, "confidence": 0.65},
                "volatility": {"predictedPct": 35.0, "confidence": 0.7},
                "anomaly": {"isAnomaly": False, "score": 0.1, "confidence": 0.78},
                "regime": {"label": "risk_on", "confidence": 0.72},
            },
        }

    monkeypatch.setattr(router_v1_module._data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategyIdeas"][0]["rationale"].startswith("ML score=")
    assert "fallback=none" in payload["dataContextSummary"]


def test_research_v2_route_uses_deterministic_ml_fallback(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Context service degraded; fallback expected.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
        }

    monkeypatch.setattr(router_v1_module._data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategyIdeas"][0]["rationale"].startswith("ML score=")
    assert "fallback=none" not in payload["dataContextSummary"]


def test_research_v2_route_normalizes_top_level_sentiment_context(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Positive sentiment trend with moderate volatility.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "sentiment": {
                "score": 68,
                "confidence": 81,
                "source": "curated-news",
                "sourceCount": 12,
                "lookbackHours": 24,
            },
            "mlSignals": {
                "prediction": {"direction": "bullish", "confidence": 0.8, "timeframe": "24h"},
                "volatility": {"predictedPct": 35.0, "confidence": 0.7},
                "anomaly": {"isAnomaly": False, "score": 0.1, "confidence": 0.76},
                "regime": {"label": "risk_on", "confidence": 0.69},
            },
        }

    router_v1_module._data_knowledge_adapter.clear_market_context_cache()
    monkeypatch.setattr(router_v1_module._base_data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategyIdeas"][0]["rationale"].startswith("ML score=")
    assert "sentiment=0.68:0.81" in payload["dataContextSummary"]
    assert "fallback=none" in payload["dataContextSummary"]
    assert "source=curated-news" in payload["dataContextSummary"]


def test_research_v2_route_handles_invalid_top_level_sentiment_with_fallback(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Sentiment pipeline degraded.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "sentiment": {"score": "bad", "confidence": "nan"},
            "mlSignals": {
                "prediction": {"direction": "neutral", "confidence": 0.6, "timeframe": "24h"},
                "volatility": {"predictedPct": 40.0, "confidence": 0.65},
                "anomaly": {"isAnomaly": False, "score": 0.1, "confidence": 0.58},
            },
        }

    router_v1_module._data_knowledge_adapter.clear_market_context_cache()
    monkeypatch.setattr(router_v1_module._base_data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategyIdeas"][0]["rationale"].startswith("ML score=")
    assert "fallback=none" not in payload["dataContextSummary"]
    assert "sentiment_score_missing" in payload["dataContextSummary"]
    assert "source=unknown" in payload["dataContextSummary"]


def test_research_v2_route_merges_dual_source_sentiment_metadata(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Sentiment metadata requires merge across dual sources.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "sentiment": {
                "score": 68,
                "confidence": 81,
                "source": "curated-news",
                "sourceCount": 12,
                "lookbackHours": 24,
            },
            "mlSignals": {
                "prediction": {"direction": "bullish", "confidence": 0.8, "timeframe": "24h"},
                "sentiment": {"score": 0.64, "confidence": 0.71},
                "volatility": {"predictedPct": 35.0, "confidence": 0.7},
                "anomaly": {"isAnomaly": False, "score": 0.1, "confidence": 0.8},
                "regime": {"label": "risk_on", "confidence": 0.75},
            },
        }

    router_v1_module._data_knowledge_adapter.clear_market_context_cache()
    monkeypatch.setattr(router_v1_module._base_data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategyIdeas"][0]["rationale"].startswith("ML score=")
    assert "sentiment=0.64:0.71" in payload["dataContextSummary"]
    assert "source=curated-news" in payload["dataContextSummary"]
    assert "lookbackHours=24" in payload["dataContextSummary"]
    assert "fallback=none" in payload["dataContextSummary"]


def test_research_v2_route_flags_risk_off_anomaly_breach_context(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Anomalous risk-off conditions detected.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "mlSignals": {
                "prediction": {"direction": "neutral", "confidence": 0.74, "timeframe": "24h"},
                "sentiment": {"score": 0.42, "confidence": 0.7},
                "volatility": {"predictedPct": 88.0, "confidence": 0.82},
                "anomaly": {"isAnomaly": True, "score": 0.93, "confidence": 0.91},
                "regime": {"label": "risk_off", "confidence": 0.86},
            },
        }

    monkeypatch.setattr(router_v1_module._data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()

    response = client.post(
        "/v2/research/market-scan",
        headers=HEADERS,
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "anomaly_breach" in payload["strategyIdeas"][0]["rationale"]
    assert "regime_risk_off" in payload["strategyIdeas"][0]["rationale"]
    assert "anomalyState=breach" in payload["dataContextSummary"]
    assert "regime=risk_off" in payload["dataContextSummary"]


def test_research_v2_snapshot_blocks_v1_order_on_anomaly_breach(monkeypatch) -> None:
    async def _market_context_stub(**_: object) -> dict[str, object]:
        return {
            "regimeSummary": "Severe anomaly regime.",
            "signals": [{"name": "focus_assets", "value": "crypto"}],
            "mlSignals": {
                "prediction": {"direction": "neutral", "confidence": 0.72, "timeframe": "24h"},
                "sentiment": {"score": 0.47, "confidence": 0.66},
                "volatility": {"predictedPct": 52.0, "confidence": 0.78},
                "anomaly": {"isAnomaly": True, "score": 0.95, "confidence": 0.92},
                "regime": {"label": "risk_off", "confidence": 0.85},
            },
        }

    original_snapshots = copy.deepcopy(router_v1_module._store.ml_signal_snapshots)
    monkeypatch.setattr(router_v1_module._data_knowledge_adapter, "get_market_context", _market_context_stub)
    client = _client()
    try:
        scan = client.post(
            "/v2/research/market-scan",
            headers=HEADERS,
            json={"assetClasses": ["crypto"], "capital": 25000},
        )
        assert scan.status_code == 200

        order = client.post(
            "/v1/orders",
            headers={**HEADERS, "Idempotency-Key": "idem-v2-risk-loop-001"},
            json={
                "symbol": "BTCUSDT",
                "side": "buy",
                "type": "limit",
                "quantity": 0.05,
                "price": 50000,
                "deploymentId": "dep-001",
            },
        )
        assert order.status_code == 423
        assert order.json()["error"]["code"] == "RISK_ML_ANOMALY_BREACH"
    finally:
        router_v1_module._store.ml_signal_snapshots = original_snapshots


def test_conversation_v2_routes() -> None:
    client = _client()

    create_session = client.post(
        "/v2/conversations/sessions",
        headers=HEADERS,
        json={
            "channel": "openclaw",
            "topic": "risk-aware deployment",
            "metadata": {"notificationsOptIn": True},
        },
    )
    assert create_session.status_code == 201
    session_payload = create_session.json()["session"]
    assert session_payload["channel"] == "openclaw"
    assert session_payload["status"] == "active"
    session_id = session_payload["id"]

    get_session = client.get(f"/v2/conversations/sessions/{session_id}", headers=HEADERS)
    assert get_session.status_code == 200
    assert get_session.json()["session"]["id"] == session_id
    assert "contextMemory" in get_session.json()["session"]["metadata"]

    create_turn = client.post(
        f"/v2/conversations/sessions/{session_id}/turns",
        headers=HEADERS,
        json={"role": "user", "message": "deploy strategy and place order"},
    )
    assert create_turn.status_code == 201
    turn_payload = create_turn.json()["turn"]
    assert turn_payload["sessionId"] == session_id
    assert len(turn_payload["suggestions"]) >= 1
    assert "contextMemorySnapshot" in turn_payload["metadata"]
    assert len(turn_payload["metadata"]["notifications"]) >= 1

    missing = client.post(
        "/v2/conversations/sessions/conv-missing/turns",
        headers=HEADERS,
        json={"role": "user", "message": "hello"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONVERSATION_SESSION_NOT_FOUND"

    null_topic = client.post(
        "/v2/conversations/sessions",
        headers=HEADERS,
        json={"channel": "web", "topic": None},
    )
    assert null_topic.status_code == 422


def test_validation_v2_routes_wire_deterministic_and_agent_outputs() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-wire-001",
        tenant_id="tenant-v2-validation",
        user_id="user-v2-validation",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-wire-001"},
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

    artifact = client.get(f"/v2/validation-runs/{run_id}/artifact", headers=headers)
    assert artifact.status_code == 200
    payload = artifact.json()
    assert payload["requestId"] == headers["X-Request-Id"]
    assert payload["artifactType"] == "validation_run"

    run_artifact = payload["artifact"]
    assert run_artifact["requestId"] == headers["X-Request-Id"]
    assert run_artifact["tenantId"] == headers["X-Tenant-Id"]
    assert run_artifact["userId"] == headers["X-User-Id"]
    assert set(run_artifact["deterministicChecks"]) == {
        "indicatorFidelity",
        "tradeCoherence",
        "metricConsistency",
    }
    assert set(run_artifact["agentReview"]) == {"status", "summary", "findings", "budget"}
    budget = run_artifact["agentReview"]["budget"]
    assert budget["profile"] == "STANDARD"
    assert set(budget["limits"]) == {"maxRuntimeSeconds", "maxTokens", "maxToolCalls", "maxFindings"}
    assert set(budget["usage"]) == {"runtimeSeconds", "tokensUsed", "toolCallsUsed"}
    assert isinstance(budget["withinBudget"], bool)
    assert run_artifact["finalDecision"] in {"pass", "conditional_pass", "fail"}


def test_validation_v2_requires_authentication() -> None:
    client = _client()

    response = client.post(
        "/v2/validation-runs",
        headers={"X-Request-Id": "req-v2-validation-unauth-001"},
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

    assert response.status_code == 401
    payload = response.json()
    assert payload["requestId"] == "req-v2-validation-unauth-001"
    assert payload["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_validation_v2_rejects_arbitrary_non_runtime_api_key() -> None:
    client = _client()
    response = client.get(
        "/v2/validation-runs",
        headers={
            "X-Request-Id": "req-v2-validation-random-key-001",
            "X-API-Key": "totally-random-key",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_validation_v2_rejects_malformed_runtime_api_key() -> None:
    client = _client()
    response = client.get(
        "/v2/validation-runs",
        headers={
            "X-Request-Id": "req-v2-validation-malformed-runtime-key-001",
            "X-API-Key": "tnx.bot.invalid",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "BOT_API_KEY_INVALID"


def test_validation_v2_rejects_unsigned_jwt_claims() -> None:
    client = _client()
    unsigned_token = (
        f"{_jwt_segment({'alg': 'none', 'typ': 'JWT'})}."
        f"{_jwt_segment({'sub': 'forged-user', 'tenant_id': 'forged-tenant'})}."
    )
    response = client.post(
        "/v2/validation-runs",
        headers={
            "Authorization": f"Bearer {unsigned_token}",
            "X-API-Key": HEADERS["X-API-Key"],
            "X-Request-Id": "req-v2-validation-forgery-unsigned-001",
            "X-Tenant-Id": "forged-tenant",
            "X-User-Id": "forged-user",
            "Idempotency-Key": "idem-v2-validation-forgery-unsigned-001",
        },
        json={
            "strategyId": "strat-001",
            "providerRefId": "lona-strategy-123",
            "prompt": "Unsigned jwt should be rejected.",
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
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_validation_v2_rejects_tampered_signed_jwt_claims() -> None:
    client = _client()
    token = _jwt_token({"sub": "user-v2-validation-tampered", "tenant_id": "tenant-v2-validation-tampered"})
    header_segment, _, signature_segment = token.split(".")
    tampered_payload = _jwt_segment({"sub": "user-v2-validation-tampered", "tenant_id": "tenant-v2-validation-other"})
    tampered_token = f"{header_segment}.{tampered_payload}.{signature_segment}"

    response = client.post(
        "/v2/validation-runs",
        headers={
            "Authorization": f"Bearer {tampered_token}",
            "X-API-Key": HEADERS["X-API-Key"],
            "X-Request-Id": "req-v2-validation-forgery-tampered-001",
            "X-Tenant-Id": "tenant-v2-validation-other",
            "X-User-Id": "user-v2-validation-tampered",
            "Idempotency-Key": "idem-v2-validation-forgery-tampered-001",
        },
        json={
            "strategyId": "strat-001",
            "providerRefId": "lona-strategy-123",
            "prompt": "Tampered jwt should be rejected.",
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
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "AUTH_UNAUTHORIZED"


def test_validation_v2_rejects_identity_header_spoofing() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-spoof-001",
        tenant_id="tenant-v2-validation-spoof",
        user_id="user-v2-validation-spoof",
        spoof_tenant_id="tenant-v2-validation-other",
    )

    response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-spoof-001"},
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

    assert response.status_code == 401
    payload = response.json()
    assert payload["requestId"] == "req-v2-validation-spoof-001"
    assert payload["error"]["code"] == "AUTH_IDENTITY_MISMATCH"
    details = payload["error"].get("details", {})
    assert details.get("header") == "X-Tenant-Id"
    assert details.get("reason") == "identity_header_mismatch"
    assert "expected" not in details
    assert "received" not in details


def test_validation_v2_uses_auth_claim_identity_without_identity_headers() -> None:
    client = _client()
    tenant_id = "tenant-v2-validation-claims"
    user_id = "user-v2-validation-claims"
    headers = _validation_headers(
        request_id="req-v2-validation-claims-001",
        tenant_id=tenant_id,
        user_id=user_id,
        include_identity_headers=False,
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-claims-001"},
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

    artifact = client.get(f"/v2/validation-runs/{run_id}/artifact", headers=headers)
    assert artifact.status_code == 200
    payload = artifact.json()["artifact"]
    assert payload["tenantId"] == tenant_id
    assert payload["userId"] == user_id


def test_validation_v2_list_runs_is_identity_scoped() -> None:
    client = _client()
    scoped_headers = _validation_headers(
        request_id="req-v2-validation-list-001",
        tenant_id="tenant-v2-validation-list",
        user_id="user-v2-validation-list",
    )
    other_headers = _validation_headers(
        request_id="req-v2-validation-list-002",
        tenant_id="tenant-v2-validation-list-other",
        user_id="user-v2-validation-list-other",
    )
    payload = {
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

    scoped_create = client.post(
        "/v2/validation-runs",
        headers={**scoped_headers, "Idempotency-Key": "idem-v2-validation-list-001"},
        json=payload,
    )
    assert scoped_create.status_code == 202
    scoped_run_id = scoped_create.json()["run"]["id"]

    other_create = client.post(
        "/v2/validation-runs",
        headers={**other_headers, "Idempotency-Key": "idem-v2-validation-list-002"},
        json=payload,
    )
    assert other_create.status_code == 202
    other_run_id = other_create.json()["run"]["id"]

    list_response = client.get("/v2/validation-runs", headers=scoped_headers)
    assert list_response.status_code == 200
    listed_ids = {item["id"] for item in list_response.json()["runs"]}
    assert scoped_run_id in listed_ids
    assert other_run_id not in listed_ids


def test_validation_v2_render_persists_optional_html_pdf_artifacts() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-render-001",
        tenant_id="tenant-v2-validation-render",
        user_id="user-v2-validation-render",
    )
    run_payload = {
        "strategyId": "strat-001",
        "providerRefId": "lona-strategy-123",
        "prompt": "Renderable validation run for html/pdf artifacts.",
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

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-render-run-001"},
        json=run_payload,
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    render_html = client.post(
        f"/v2/validation-runs/{run_id}/render",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-render-html-001"},
        json={"format": "html"},
    )
    assert render_html.status_code == 202
    render_html_payload = render_html.json()["render"]
    assert render_html_payload["status"] == "completed"
    assert render_html_payload["artifactRef"] == f"blob://validation/{run_id}/report.html"

    render_pdf = client.post(
        f"/v2/validation-runs/{run_id}/render",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-render-pdf-001"},
        json={"format": "pdf"},
    )
    assert render_pdf.status_code == 202
    render_pdf_payload = render_pdf.json()["render"]
    assert render_pdf_payload["status"] == "completed"
    assert render_pdf_payload["artifactRef"] == f"blob://validation/{run_id}/report.pdf"

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_run(  # noqa: SLF001
            run_id=run_id,
            tenant_id=headers["X-Tenant-Id"],
            user_id=headers["X-User-Id"],
        )
    )
    assert persisted is not None
    refs = {item.kind: item for item in persisted.blob_refs}
    assert refs["render_html"].ref == render_html_payload["artifactRef"]
    assert refs["render_html"].content_type == "text/html; charset=utf-8"
    assert refs["render_pdf"].ref == render_pdf_payload["artifactRef"]
    assert refs["render_pdf"].content_type == "application/pdf"


def test_validation_v2_render_failure_is_auditable_and_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingRenderer:
        def render(self, *, artifact: object, output_format: str) -> object:
            _ = (artifact, output_format)
            raise RuntimeError("simulated-render-failure")

    monkeypatch.setattr(router_v2_module._validation_service, "_renderer", _FailingRenderer())  # noqa: SLF001

    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-render-fail-001",
        tenant_id="tenant-v2-validation-render-fail",
        user_id="user-v2-validation-render-fail",
    )
    run_payload = {
        "strategyId": "strat-001",
        "providerRefId": "lona-strategy-123",
        "prompt": "Validation run where optional renderer fails.",
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

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-render-fail-run-001"},
        json=run_payload,
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    render_response = client.post(
        f"/v2/validation-runs/{run_id}/render",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-render-fail-html-001"},
        json={"format": "html"},
    )
    assert render_response.status_code == 202
    render_payload = render_response.json()["render"]
    assert render_payload["status"] == "failed"
    assert render_payload["artifactRef"] == f"blob://validation/{run_id}/render-html-failure.json"

    artifact_response = client.get(f"/v2/validation-runs/{run_id}/artifact", headers=headers)
    assert artifact_response.status_code == 200
    assert artifact_response.json()["artifactType"] == "validation_run"

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_run(  # noqa: SLF001
            run_id=run_id,
            tenant_id=headers["X-Tenant-Id"],
            user_id=headers["X-User-Id"],
        )
    )
    assert persisted is not None
    refs = {item.kind: item for item in persisted.blob_refs}
    assert refs["render_html"].ref == render_payload["artifactRef"]
    assert refs["render_html"].content_type == "application/json"
    assert "backtest_report" in refs


def test_validation_v2_trader_conditional_pass_is_reviewed_but_not_fully_passed() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-trader-001",
        tenant_id="tenant-v2-validation-trader",
        user_id="user-v2-validation-trader",
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-trader-run-001"},
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
                "blockMergeOnAgentFail": False,
                "blockReleaseOnAgentFail": False,
                "requireTraderReview": True,
                "hardFailOnMissingIndicators": True,
                "failClosedOnEvidenceUnavailable": True,
            },
        },
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    before_review = client.get(f"/v2/validation-runs/{run_id}/artifact", headers=headers)
    assert before_review.status_code == 200
    assert before_review.json()["artifact"]["traderReview"]["status"] == "requested"

    review_response = client.post(
        f"/v2/validation-runs/{run_id}/review",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-trader-review-001"},
        json={
            "reviewerType": "trader",
            "decision": "conditional_pass",
            "summary": "Approved with caution on market volatility regime shifts.",
            "comments": ["Needs guardrails before rollout."],
            "findings": [],
        },
    )
    assert review_response.status_code == 202

    after_review = client.get(f"/v2/validation-runs/{run_id}/artifact", headers=headers)
    assert after_review.status_code == 200
    artifact = after_review.json()["artifact"]
    assert artifact["traderReview"]["status"] == "approved"
    assert artifact["finalDecision"] == "conditional_pass"

    run = client.get(f"/v2/validation-runs/{run_id}", headers=headers)
    assert run.status_code == 200
    assert run.json()["run"]["finalDecision"] == "conditional_pass"

    agent_follow_up_review = client.post(
        f"/v2/validation-runs/{run_id}/review",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-trader-agent-follow-up-001"},
        json={
            "reviewerType": "agent",
            "decision": "pass",
            "summary": "No additional deterministic or evidence issues.",
            "findings": [],
            "comments": [],
        },
    )
    assert agent_follow_up_review.status_code == 202

    run_after_agent = client.get(f"/v2/validation-runs/{run_id}", headers=headers)
    assert run_after_agent.status_code == 200
    assert run_after_agent.json()["run"]["finalDecision"] == "conditional_pass"


def test_validation_v2_create_run_idempotency_and_conflict() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-idem-001",
        tenant_id="tenant-v2-validation-idem",
        user_id="user-v2-validation-idem",
    )
    headers["Idempotency-Key"] = "idem-v2-validation-run-001"
    payload = {
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

    first = client.post("/v2/validation-runs", headers=headers, json=payload)
    assert first.status_code == 202
    second = client.post("/v2/validation-runs", headers=headers, json=payload)
    assert second.status_code == 202
    assert second.json()["run"]["id"] == first.json()["run"]["id"]

    conflict = client.post(
        "/v2/validation-runs",
        headers=headers,
        json={**payload, "prompt": "different payload"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_validation_v2_rejects_invalid_policy_profile_and_state() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-neg-001",
        tenant_id="tenant-v2-validation-neg",
        user_id="user-v2-validation-neg",
    )
    base_payload = {
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

    invalid_profile = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-neg-profile-001"},
        json={**base_payload, "policy": {**base_payload["policy"], "profile": "ULTRA"}},
    )
    assert invalid_profile.status_code == 400
    assert invalid_profile.json()["requestId"] == headers["X-Request-Id"]
    assert invalid_profile.json()["error"]["code"] == "VALIDATION_POLICY_INVALID"

    invalid_policy = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-neg-policy-001"},
        json={
            **base_payload,
            "policy": {**base_payload["policy"], "hardFailOnMissingIndicators": False},
        },
    )
    assert invalid_policy.status_code == 400
    assert invalid_policy.json()["requestId"] == headers["X-Request-Id"]
    assert invalid_policy.json()["error"]["code"] == "VALIDATION_POLICY_INVALID"

    invalid_state = client.post(
        "/v2/validation-baselines",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-neg-state-001"},
        json={
            "runId": "valrun-missing",
            "name": "missing-run-baseline",
        },
    )
    assert invalid_state.status_code == 400
    assert invalid_state.json()["requestId"] == headers["X-Request-Id"]
    assert invalid_state.json()["error"]["code"] == "VALIDATION_STATE_INVALID"

    invalid_replay_state = client.post(
        "/v2/validation-regressions/replay",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-neg-replay-state-001"},
        json={
            "baselineId": "valbase-missing",
            "candidateRunId": "valrun-missing",
        },
    )
    assert invalid_replay_state.status_code == 400
    assert invalid_replay_state.json()["requestId"] == headers["X-Request-Id"]
    assert invalid_replay_state.json()["error"]["code"] == "VALIDATION_STATE_INVALID"

    invalid_replay_policy_override = client.post(
        "/v2/validation-regressions/replay",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-neg-replay-override-001"},
        json={
            "baselineId": "valbase-missing",
            "candidateRunId": "valrun-missing",
            "policyOverrides": {"blockMergeOnFail": False},
        },
    )
    assert invalid_replay_policy_override.status_code == 400
    assert invalid_replay_policy_override.json()["requestId"] == headers["X-Request-Id"]
    assert invalid_replay_policy_override.json()["error"]["code"] == "VALIDATION_REPLAY_INVALID"


def test_validation_v2_rejects_widened_enum_and_nullable_inputs() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-inputs-001",
        tenant_id="tenant-v2-validation-inputs",
        user_id="user-v2-validation-inputs",
    )
    base_payload = {
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

    null_provider_ref = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-null-provider-001"},
        json={**base_payload, "providerRefId": None},
    )
    assert null_provider_ref.status_code == 400
    assert null_provider_ref.json()["error"]["code"] == "VALIDATION_RUN_INVALID"

    null_prompt = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-null-prompt-001"},
        json={**base_payload, "prompt": None},
    )
    assert null_prompt.status_code == 400
    assert null_prompt.json()["error"]["code"] == "VALIDATION_RUN_INVALID"

    unknown_strategy = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-missing-strategy-001"},
        json={**base_payload, "strategyId": "strat-missing"},
    )
    assert unknown_strategy.status_code == 400
    assert unknown_strategy.json()["error"]["code"] == "VALIDATION_STATE_INVALID"

    create_run = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-run-001"},
        json=base_payload,
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    review_upper_reviewer = client.post(
        f"/v2/validation-runs/{run_id}/review",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-review-upper-reviewer-001"},
        json={
            "reviewerType": "AGENT",
            "decision": "pass",
            "summary": "Uppercase reviewer type should be rejected.",
            "findings": [],
            "comments": [],
        },
    )
    assert review_upper_reviewer.status_code == 400
    assert review_upper_reviewer.json()["error"]["code"] == "VALIDATION_REVIEW_INVALID"

    review_upper_decision = client.post(
        f"/v2/validation-runs/{run_id}/review",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-review-upper-decision-001"},
        json={
            "reviewerType": "agent",
            "decision": "PASS",
            "summary": "Uppercase decision should be rejected.",
            "findings": [],
            "comments": [],
        },
    )
    assert review_upper_decision.status_code == 400
    assert review_upper_decision.json()["error"]["code"] == "VALIDATION_REVIEW_INVALID"

    render_upper_format = client.post(
        f"/v2/validation-runs/{run_id}/render",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-inputs-render-upper-001"},
        json={"format": "HTML"},
    )
    assert render_upper_format.status_code == 400
    assert render_upper_format.json()["error"]["code"] == "VALIDATION_RENDER_INVALID"


def test_validation_v2_blocks_provider_ref_bypass() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-provider-001",
        tenant_id="tenant-v2-validation-provider",
        user_id="user-v2-validation-provider",
    )

    response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-provider-001"},
        json={
            "strategyId": "strat-001",
            "providerRefId": "external-provider-direct-bypass",
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
    assert response.status_code == 400
    payload = response.json()
    assert payload["requestId"] == headers["X-Request-Id"]
    assert payload["error"]["code"] == "VALIDATION_PROVIDER_REF_MISMATCH"


def test_validation_v2_replay_treats_candidate_improvement_as_pass() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-replay-001",
        tenant_id="tenant-v2-validation-replay",
        user_id="user-v2-validation-replay",
    )
    run_payload = {
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

    baseline_run_response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-baseline-run-001"},
        json={**run_payload, "policy": {**run_payload["policy"], "profile": "EXPERT"}},
    )
    assert baseline_run_response.status_code == 202
    baseline_run_id = baseline_run_response.json()["run"]["id"]

    baseline_run = client.get(f"/v2/validation-runs/{baseline_run_id}", headers=headers)
    assert baseline_run.status_code == 200
    assert baseline_run.json()["run"]["finalDecision"] == "fail"

    candidate_run_response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-candidate-run-001"},
        json=run_payload,
    )
    assert candidate_run_response.status_code == 202
    candidate_run_id = candidate_run_response.json()["run"]["id"]

    candidate_review = client.post(
        f"/v2/validation-runs/{candidate_run_id}/review",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-candidate-review-001"},
        json={
            "reviewerType": "agent",
            "decision": "pass",
            "summary": "Candidate run is acceptable.",
            "findings": [],
            "comments": [],
        },
    )
    assert candidate_review.status_code == 202

    candidate_run = client.get(f"/v2/validation-runs/{candidate_run_id}", headers=headers)
    assert candidate_run.status_code == 200
    assert candidate_run.json()["run"]["finalDecision"] == "pass"

    baseline_response = client.post(
        "/v2/validation-baselines",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-baseline-001"},
        json={"runId": baseline_run_id, "name": "expert-baseline"},
    )
    assert baseline_response.status_code == 201
    baseline_id = baseline_response.json()["baseline"]["id"]

    replay = client.post(
        "/v2/validation-regressions/replay",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-request-001"},
        json={"baselineId": baseline_id, "candidateRunId": candidate_run_id},
    )
    assert replay.status_code == 202
    replay_payload = replay.json()["replay"]
    assert replay_payload["status"] == "completed"
    assert replay_payload["decision"] == "pass"
    assert replay_payload["mergeBlocked"] is False
    assert replay_payload["releaseBlocked"] is False
    assert replay_payload["mergeGateStatus"] == "pass"
    assert replay_payload["releaseGateStatus"] == "pass"
    assert replay_payload["baselineDecision"] == "fail"
    assert replay_payload["candidateDecision"] == "pass"
    assert replay_payload["thresholdBreached"] is False
    assert replay_payload["reasons"] == []

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_replay(  # noqa: SLF001
            replay_id=replay_payload["id"],
            tenant_id=headers["X-Tenant-Id"],
            user_id=headers["X-User-Id"],
        )
    )
    assert persisted is not None
    assert persisted.release_blocked is False
    assert persisted.release_gate_status == "pass"


def test_validation_v2_replay_failure_blocks_merge_and_release_by_policy() -> None:
    client = _client()
    headers = _validation_headers(
        request_id="req-v2-validation-replay-gates-001",
        tenant_id="tenant-v2-validation-replay-gates",
        user_id="user-v2-validation-replay-gates",
    )

    baseline_run_response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-gates-baseline-run-001"},
        json={
            "strategyId": "strat-001",
            "providerRefId": "lona-strategy-123",
            "prompt": "Baseline run for replay gates.",
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
    assert baseline_run_response.status_code == 202
    baseline_run_id = baseline_run_response.json()["run"]["id"]
    baseline_run = client.get(f"/v2/validation-runs/{baseline_run_id}", headers=headers)
    assert baseline_run.status_code == 200
    assert baseline_run.json()["run"]["finalDecision"] == "pass"

    baseline_response = client.post(
        "/v2/validation-baselines",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-gates-baseline-001"},
        json={"runId": baseline_run_id, "name": "gates-baseline"},
    )
    assert baseline_response.status_code == 201
    baseline_id = baseline_response.json()["baseline"]["id"]

    candidate_run_response = client.post(
        "/v2/validation-runs",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-gates-candidate-run-001"},
        json={
            "strategyId": "strat-001",
            "providerRefId": "lona-strategy-123",
            "prompt": "Candidate run with stricter profile to force deterministic fail.",
            "requestedIndicators": ["zigzag", "ema"],
            "datasetIds": ["dataset-btc-1h-2025"],
            "backtestReportRef": "blob://validation/candidate/backtest-report.json",
            "policy": {
                "profile": "EXPERT",
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
    assert candidate_run_response.status_code == 202
    candidate_run_id = candidate_run_response.json()["run"]["id"]
    candidate_run = client.get(f"/v2/validation-runs/{candidate_run_id}", headers=headers)
    assert candidate_run.status_code == 200
    assert candidate_run.json()["run"]["finalDecision"] == "fail"

    replay = client.post(
        "/v2/validation-regressions/replay",
        headers={**headers, "Idempotency-Key": "idem-v2-validation-replay-gates-request-001"},
        json={"baselineId": baseline_id, "candidateRunId": candidate_run_id},
    )
    assert replay.status_code == 202
    replay_payload = replay.json()["replay"]
    assert replay_payload["status"] == "completed"
    assert replay_payload["decision"] == "fail"
    assert replay_payload["mergeBlocked"] is True
    assert replay_payload["releaseBlocked"] is True
    assert replay_payload["mergeGateStatus"] == "blocked"
    assert replay_payload["releaseGateStatus"] == "blocked"
    assert replay_payload["baselineDecision"] == "pass"
    assert replay_payload["candidateDecision"] == "fail"
    assert "candidate_decision_regressed_from_baseline" in replay_payload["reasons"]

    persisted = asyncio.run(
        router_v2_module._validation_service._validation_storage.get_replay(  # noqa: SLF001
            replay_id=replay_payload["id"],
            tenant_id=headers["X-Tenant-Id"],
            user_id=headers["X-User-Id"],
        )
    )
    assert persisted is not None
    assert persisted.merge_blocked is True
    assert persisted.release_blocked is True


def test_backtest_feedback_is_ingested_into_kb() -> None:
    client = _client()

    create_strategy = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "KB Feedback Strategy",
            "description": "Strategy to validate KB feedback ingestion.",
            "provider": "xai",
        },
    )
    assert create_strategy.status_code == 201
    strategy_id = create_strategy.json()["strategy"]["id"]

    create_backtest = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "dataIds": ["dataset-btc-1h-2025"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert create_backtest.status_code == 202
    backtest_id = create_backtest.json()["backtest"]["id"]

    get_backtest = client.get(f"/v1/backtests/{backtest_id}", headers=HEADERS)
    assert get_backtest.status_code == 200

    search = client.post(
        "/v2/knowledge/search",
        headers=HEADERS,
        json={"query": backtest_id, "assets": [], "limit": 20},
    )
    assert search.status_code == 200
    items = search.json()["items"]
    assert any(item["kind"] == "lesson" and backtest_id in item["summary"] for item in items)
