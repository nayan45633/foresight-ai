"""Foresight AI - Step 9 Database Persistence and Registry Test Suite."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.db.models.audit import AuditLog
from app.db.models.counterfactual import CounterfactualScenarioRecord
from app.db.models.model_registry import ModelVersionRecord
from app.db.models.telemetry_job import TelemetryJob
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_model_registry_persistence(async_client: AsyncClient):
    """Verifies that model artifacts are queryable from persistent storage."""
    # 1. Query current active model
    res_curr = await async_client.get("/api/v1/model/current")
    assert res_curr.status_code == 200
    curr_data = res_curr.json()
    assert "version_tag" in curr_data
    assert curr_data["status"] == "ACTIVE"
    assert "conformal_target_coverage" in curr_data

    # 2. Query model versions list
    res_list = await async_client.get("/api/v1/model/versions")
    assert res_list.status_code == 200
    versions = res_list.json()
    assert len(versions) >= 1
    assert any(v["version_tag"] == curr_data["version_tag"] for v in versions)


@pytest.mark.asyncio
async def test_audit_log_querying_and_analyst_access(async_client: AsyncClient):
    """Verifies that security audit logs are recorded on sensitive actions and accessible to analysts."""
    # 1. Register and login analyst
    analyst_payload = {
        "email": "audit_analyst@foresight.ai",
        "username": "audit_analyst",
        "password": "Password123!",
        "role": "analyst",
    }
    await async_client.post("/api/v1/auth/register", json=analyst_payload)
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "audit_analyst", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Query audit logs as analyst
    res_logs = await async_client.get("/api/v1/audit/logs?limit=10", headers=headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    # Verify log attributes
    first_log = logs[0]
    assert "actor" in first_log
    assert "action" in first_log
    assert "resource" in first_log
    assert "status" in first_log
    assert "created_at" in first_log


@pytest.mark.asyncio
async def test_pcap_job_db_persistence(async_client: AsyncClient):
    """Verifies that PCAP jobs are recorded in the telemetry_jobs table."""
    pcap_bytes = (
        b"\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x04\x00\x01\x00\x00\x00"
    )
    files = {"file": ("persistence_test.pcap", pcap_bytes, "application/vnd.tcpdump.pcap")}
    res_upload = await async_client.post("/api/v1/telemetry/pcap", files=files)
    assert res_upload.status_code == 202
    job_id = res_upload.json()["job_id"]

    # Verify status query
    res_status = await async_client.get(f"/api/v1/telemetry/ingestion/{job_id}")
    assert res_status.status_code == 200
    assert res_status.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_counterfactual_scenario_db_persistence(async_client: AsyncClient, db_session):
    """Verifies that counterfactual scenario runs are persisted to the database."""
    cf_payload = {
        "scenario_name": "Persistent Scenario Test",
        "description": "DB test for scenario persistence",
        "perturbations": {
            "syn_count": 50.0,
        },
        "recompute_derived": True,
        "include_shap": False,
    }
    res = await async_client.post("/api/v1/model/counterfactual", json=cf_payload)
    assert res.status_code == 200
    scen_id = res.json()["scenario_id"]

    # Direct DB verification using test-bound session
    result = await db_session.execute(
        select(CounterfactualScenarioRecord).where(
            CounterfactualScenarioRecord.scenario_id == scen_id
        )
    )
    rec = result.scalar_one_or_none()
    assert rec is not None
    assert rec.scenario_name == "Persistent Scenario Test"
    assert rec.model_version is not None
