"""Contract tests for structured observability fields (R-01)."""

from __future__ import annotations

import copy
import logging

from fastapi.testclient import TestClient

from src.main import app
from src.platform_api import router_v1 as router_v1_module


def _client() -> TestClient:
    return TestClient(app)


def _records_by_component(caplog, component: str) -> list[logging.LogRecord]:  # type: ignore[no-untyped-def]
    return [record for record in caplog.records if getattr(record, "component", None) == component]


def _assert_identity_fields(record: logging.LogRecord, *, request_id: str, tenant_id: str, user_id: str) -> None:
    assert getattr(record, "requestId", None) == request_id
    assert getattr(record, "tenantId", None) == tenant_id
    assert getattr(record, "userId", None) == user_id
    assert isinstance(getattr(record, "operation", None), str)
    assert getattr(record, "operation", None) != ""


def test_structured_observability_fields_for_research_risk_and_execution(caplog) -> None:
    client = _client()
    caplog.set_level(logging.INFO)

    original_policy = copy.deepcopy(router_v1_module._store.risk_policy)
    original_snapshots = copy.deepcopy(router_v1_module._store.ml_signal_snapshots)
    try:
        router_v1_module._store.ml_signal_snapshots = {}
        router_v1_module._store.risk_policy["limits"]["maxNotionalUsd"] = 2_000_000
        router_v1_module._store.risk_policy["limits"]["maxPositionNotionalUsd"] = 500_000

        research_resp = client.post(
            "/v2/research/market-scan",
            headers={
                "Authorization": "Bearer test-token",
                "X-API-Key": "test-key",
                "X-Request-Id": "req-obs-rsch-001",
                "X-Tenant-Id": "tenant-obs",
                "X-User-Id": "user-obs",
            },
            json={"assetClasses": ["crypto"], "capital": 25000},
        )
        assert research_resp.status_code == 200

        order_resp = client.post(
            "/v1/orders",
            headers={
                "Authorization": "Bearer test-token",
                "X-API-Key": "test-key",
                "X-Request-Id": "req-obs-exec-001",
                "X-Tenant-Id": "tenant-obs",
                "X-User-Id": "user-obs",
                "Idempotency-Key": "idem-obs-order-001",
            },
            json={
                "symbol": "BTCUSDT",
                "side": "buy",
                "type": "limit",
                "quantity": 0.05,
                "price": 50000,
                "deploymentId": "dep-001",
            },
        )
        assert order_resp.status_code == 201
    finally:
        router_v1_module._store.risk_policy = original_policy
        router_v1_module._store.ml_signal_snapshots = original_snapshots

    research_records = _records_by_component(caplog, "research")
    risk_records = _records_by_component(caplog, "risk")
    execution_records = _records_by_component(caplog, "execution")

    assert research_records
    assert risk_records
    assert execution_records

    _assert_identity_fields(research_records[-1], request_id="req-obs-rsch-001", tenant_id="tenant-obs", user_id="user-obs")
    _assert_identity_fields(risk_records[-1], request_id="req-obs-exec-001", tenant_id="tenant-obs", user_id="user-obs")
    _assert_identity_fields(execution_records[-1], request_id="req-obs-exec-001", tenant_id="tenant-obs", user_id="user-obs")

    assert any(getattr(record, "resourceType", None) == "order" for record in risk_records)
    assert any(getattr(record, "resourceType", None) == "order" for record in execution_records)


def test_v2_request_context_falls_back_for_blank_identity_headers(caplog) -> None:
    client = _client()
    caplog.set_level(logging.INFO)
    caplog.clear()

    response = client.post(
        "/v2/research/market-scan",
        headers={
            "Authorization": "Bearer test-token",
            "X-API-Key": "test-key",
            "X-Request-Id": "req-obs-blank-identity-001",
            "X-Tenant-Id": "   ",
            "X-User-Id": "",
        },
        json={"assetClasses": ["crypto"], "capital": 25000},
    )
    assert response.status_code == 200

    api_records = _records_by_component(caplog, "api")
    research_records = _records_by_component(caplog, "research")
    assert api_records
    assert research_records

    request_records = [
        record
        for record in api_records
        if getattr(record, "requestId", None) == "req-obs-blank-identity-001"
    ]
    assert request_records
    for record in request_records:
        assert getattr(record, "tenantId", None) == "tenant-local"
        assert getattr(record, "userId", None) == "user-local"

    research_record = next(
        record
        for record in reversed(research_records)
        if getattr(record, "requestId", None) == "req-obs-blank-identity-001"
    )
    assert getattr(research_record, "tenantId", None) == "tenant-local"
    assert getattr(research_record, "userId", None) == "user-local"


def test_structured_observability_fields_for_conversation_and_reconciliation(caplog) -> None:
    client = _client()
    caplog.set_level(logging.INFO)
    caplog.clear()

    router_v1_module._execution_service._last_reconciliation_run_by_scope["deployments"] = 0.0

    create_session = client.post(
        "/v2/conversations/sessions",
        headers={
            "Authorization": "Bearer test-token",
            "X-API-Key": "test-key",
            "X-Request-Id": "req-obs-conv-001",
            "X-Tenant-Id": "tenant-obs",
            "X-User-Id": "user-obs",
        },
        json={"channel": "web", "topic": "observability test"},
    )
    assert create_session.status_code == 201

    list_deployments = client.get(
        "/v1/deployments",
        headers={
            "Authorization": "Bearer test-token",
            "X-API-Key": "test-key",
            "X-Request-Id": "req-obs-recon-001",
            "X-Tenant-Id": "tenant-obs",
            "X-User-Id": "user-obs",
        },
    )
    assert list_deployments.status_code == 200

    conversation_records = _records_by_component(caplog, "conversation")
    reconciliation_records = _records_by_component(caplog, "reconciliation")

    assert conversation_records
    assert reconciliation_records

    _assert_identity_fields(
        conversation_records[-1],
        request_id="req-obs-conv-001",
        tenant_id="tenant-obs",
        user_id="user-obs",
    )
    _assert_identity_fields(
        reconciliation_records[-1],
        request_id="req-obs-recon-001",
        tenant_id="tenant-obs",
        user_id="user-obs",
    )
    assert getattr(reconciliation_records[-1], "resourceType", None) == "reconciliation"
