"""API tests."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


def test_root(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


def test_health(client: TestClient) -> None:
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_health(client: TestClient) -> None:
    """Test API health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "trade-nexus-ml"


@pytest.mark.asyncio
async def test_predict_endpoint(client: TestClient) -> None:
    """Test prediction endpoint."""
    response = client.post(
        "/api/predict",
        json={
            "symbol": "BTC",
            "prediction_type": "price",
            "timeframe": "24h",
            "features": {"current_price": 50000, "momentum": 0.5},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "value" in data
    assert "confidence" in data


@pytest.mark.asyncio
async def test_anomaly_endpoint(client: TestClient) -> None:
    """Test anomaly detection endpoint."""
    response = client.post(
        "/api/anomaly",
        json={
            "symbol": "BTC",
            "data": [100, 101, 102, 103, 150],  # Last value is anomalous
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "is_anomaly" in data
    assert "score" in data


@pytest.mark.asyncio
async def test_optimize_endpoint(client: TestClient) -> None:
    """Test portfolio optimization endpoint."""
    response = client.post(
        "/api/optimize",
        json={
            "holdings": {"BTC": 1.0, "ETH": 10.0},
            "predictions": [
                {"symbol": "BTC", "confidence": 70, "value": {"direction": "bullish"}},
                {"symbol": "ETH", "confidence": 60, "value": {"direction": "bullish"}},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "allocations" in data
    assert "expected_return" in data
