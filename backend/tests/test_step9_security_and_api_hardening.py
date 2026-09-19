"""Foresight AI - Step 9 Security, Rate Limiting, and API Hardening Test Suite."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_middleware(async_client: AsyncClient):
    """Verifies that security defensive headers are applied to all API responses."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age" in headers.get("Strict-Transport-Security", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_request_id_and_process_time_headers(async_client: AsyncClient):
    """Verifies that RequestLoggingMiddleware injects X-Request-ID and X-Process-Time."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_rate_limiting_headers(async_client: AsyncClient):
    """Verifies that rate limit telemetry headers are returned on API requests."""
    response = await async_client.get("/api/v1/model/current")
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


@pytest.mark.asyncio
async def test_structured_error_responses(async_client: AsyncClient):
    """Verifies that 401, 404, and 422 responses follow the production structured error schema."""
    # 1. 401 Unauthorized
    res_401 = await async_client.get("/api/v1/auth/me")
    assert res_401.status_code == 401
    data_401 = res_401.json()
    assert "error" in data_401
    assert data_401["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in data_401["error"]
    assert "message" in data_401["error"]

    # 2. 404 Not Found
    res_404 = await async_client.get("/api/v1/model/counterfactual/scenario/non-existent-id")
    assert res_404.status_code == 404
    data_404 = res_404.json()
    assert "error" in data_404
    assert data_404["error"]["code"] == "NOT_FOUND"

    # 3. 422 Unprocessable Entity
    res_422 = await async_client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert "error" in data_422
    assert data_422["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(data_422["error"]["details"], list)


@pytest.mark.asyncio
async def test_health_and_readiness_probes(async_client: AsyncClient):
    """Verifies that health and readiness probes report system, DB, and model status."""
    # Health Probe
    res_health = await async_client.get("/api/v1/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert "timestamp" in health_data
    assert "python_version" in health_data

    # Readiness Probe
    res_ready = await async_client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"
    assert ready_data["database"] == "ok"
    assert "active_model_version" in ready_data
