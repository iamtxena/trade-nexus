"""Tests for CORS allowlist and security response headers."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# CORS origin tests
# ---------------------------------------------------------------------------

class TestCORSOrigins:
    """Verify that the CORS allowlist accepts production and dev origins."""

    def test_production_web_origin_allowed(self, client: TestClient) -> None:
        response = client.get(
            "/health",
            headers={"Origin": "https://trade-nexus.lona.agency"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://trade-nexus.lona.agency"

    def test_localhost_origin_allowed(self, client: TestClient) -> None:
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_production_api_origin_allowed(self, client: TestClient) -> None:
        response = client.get(
            "/health",
            headers={"Origin": "https://api-nexus.lona.agency"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://api-nexus.lona.agency"

    def test_unlisted_origin_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/health",
            headers={"Origin": "https://evil.example.com"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Security headers tests
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    """Verify that security headers are present on all responses."""

    def test_strict_transport_security(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"

    def test_x_content_type_options(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_x_frame_options(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["x-frame-options"] == "DENY"

    def test_referrer_policy(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_security_headers_on_root(self, client: TestClient) -> None:
        """Security headers must appear on every route, not just /health."""
        response = client.get("/")
        assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
