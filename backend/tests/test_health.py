"""Foresight AI - Test System Health and Core Readiness."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Foresight" in data["name"]
    assert "docs_url" in data


@pytest.mark.asyncio
async def test_health_probe(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "python_version" in data


@pytest.mark.asyncio
async def test_readiness_probe(async_client: AsyncClient):
    response = await async_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
