"""Runtime checks for ErrorResponse envelope parity."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app
from src.platform_api import router_v1


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "tnx.bot.runtime-contract-001.secret-001",
    "X-Request-Id": "req-error-envelope-001",
}


def _assert_error_envelope(payload: dict[str, object]) -> None:
    assert "requestId" in payload
    assert "error" in payload
    error = payload["error"]
    assert isinstance(error, dict)
    assert "code" in error
    assert "message" in error


def test_platform_error_handler_not_registered_globally() -> None:
    assert Exception not in app.exception_handlers


def test_404_responses_use_error_envelope() -> None:
    client = TestClient(app)

    strategy = client.get("/v1/strategies/strat-missing", headers=HEADERS)
    assert strategy.status_code == 404
    _assert_error_envelope(strategy.json())

    deployment = client.get("/v1/deployments/dep-missing", headers=HEADERS)
    assert deployment.status_code == 404
    _assert_error_envelope(deployment.json())

    dataset = client.get("/v1/datasets/dataset-missing", headers=HEADERS)
    assert dataset.status_code == 404
    _assert_error_envelope(dataset.json())


def test_409_responses_use_error_envelope() -> None:
    client = TestClient(app)

    first = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-error-envelope-001"},
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": 0.1,
            "price": 64000,
            "deploymentId": "dep-001",
        },
    )
    assert first.status_code == 201

    conflict = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-error-envelope-001"},
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": 0.2,
            "price": 64000,
            "deploymentId": "dep-001",
        },
    )
    assert conflict.status_code == 409
    _assert_error_envelope(conflict.json())


def test_unhandled_errors_use_error_envelope(monkeypatch) -> None:
    async def _raise_unhandled(**_: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(router_v1._dataset_service, "init_upload", _raise_unhandled)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/datasets/uploads:init",
        headers=HEADERS,
        json={
            "filename": "broken.csv",
            "contentType": "text/csv",
            "sizeBytes": 128,
        },
    )

    assert response.status_code == 500
    payload = response.json()
    _assert_error_envelope(payload)
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["requestId"] == HEADERS["X-Request-Id"]
