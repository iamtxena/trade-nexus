"""Contract-oriented smoke tests for Platform API v2 handlers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-v2-contract-001",
}


def _client() -> TestClient:
    return TestClient(app)


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


def test_conversation_v2_routes() -> None:
    client = _client()

    create_session = client.post(
        "/v2/conversations/sessions",
        headers=HEADERS,
        json={"channel": "openclaw", "topic": "risk-aware deployment"},
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
