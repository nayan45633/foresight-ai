"""Foresight AI - Integration Tests for Authentication, Telemetry, and Forecasting APIs."""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow(async_client: AsyncClient):
    # 1. Register User
    reg_payload = {
        "email": "analyst@foresight.sec",
        "username": "soc_analyst_01",
        "password": "SecurePassword#2026",
        "full_name": "Senior SOC Analyst",
        "role": "analyst",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["username"] == "soc_analyst_01"
    assert user_data["email"] == "analyst@foresight.sec"
    assert "hashed_password" not in user_data

    # 2. Login
    login_payload = {
        "username_or_email": "soc_analyst_01",
        "password": "SecurePassword#2026",
    }
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Access Protected /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "soc_analyst_01"


@pytest.mark.asyncio
async def test_telemetry_flow_ingestion(async_client: AsyncClient):
    now_iso = datetime.now(timezone.utc).isoformat()
    flow_payload = {
        "source_identifier": "sensor-perimeter-alpha",
        "flows": [
            {
                "timestamp": now_iso,
                "source_ip": "192.168.10.50",
                "destination_ip": "10.0.0.100",
                "source_port": 49152,
                "destination_port": 443,
                "protocol": "TCP",
                "flow_duration_ms": 250.0,
                "packet_count": 25,
                "byte_count": 14200,
                "packet_rate": 100.0,
                "byte_rate": 56800.0,
                "tcp_flags": "SYN,ACK",
                "connection_state": "ESTABLISHED",
                "direction": "ingress",
                "metadata": {"sensor_vlan": 100},
            }
        ],
    }

    res = await async_client.post("/api/v1/telemetry/flows", json=flow_payload)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "ACCEPTED"
    assert data["records_received"] == 1

    # Verify recent flows retrieval
    recent_res = await async_client.get("/api/v1/telemetry/recent")
    assert recent_res.status_code == 200
    recent_flows = recent_res.json()
    assert len(recent_flows) >= 1
    assert recent_flows[0]["source_ip"] == "192.168.10.50"


@pytest.mark.asyncio
async def test_model_status_and_calibration_endpoints(async_client: AsyncClient):
    status_res = await async_client.get("/api/v1/model/status")
    assert status_res.status_code == 200
    assert "version_tag" in status_res.json()

    calib_res = await async_client.get("/api/v1/model/calibration")
    assert calib_res.status_code == 200
    calib_data = calib_res.json()
    assert "brier_score" in calib_data
    assert "expected_calibration_error" in calib_data
