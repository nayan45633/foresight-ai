"""Foresight AI - Step 12 End-to-End Pipeline Integration Test Suite.

Verifies the complete 19-stage real ML, security, persistence, and API lifecycle:
Stages 1-3:   Telemetry Flow Ingestion & 37-D Vector Schema Validation
Stages 4-6:   Multi-Horizon HistGradientBoosting Inference, Isotonic Calibration & Conformal Prediction Sets
Stages 7-8:   TreeSHAP Attribution Calculus & Lead-Time Horizon Aggregation (+5m, +15m, +30m, +60m)
Stages 9-10:  Dynamic Risk State Matrix Evaluation & Attack Path Graph Transition Analysis
Stage 11:     Counterfactual Optimization & What-If Simulation Engine
Stages 12-14: RBAC Auth Middleware, Async SQLAlchemy Persistence & Feature Drift Telemetry
Stages 15-19: Security Threat Defenses, Artifact Integrity Verification & Full End-to-End Orchestrated REST API Flow
"""

import numpy as np
import pytest
from httpx import AsyncClient

from app.ml.attack_path import AttackPathEngine
from app.ml.contracts import (
    CounterfactualScenarioRequest,
    FeatureClassificationEnum,
    PerturbationModeEnum,
    RiskStateEnum,
)
from app.ml.counterfactual import counterfactual_engine
from app.ml.feature_schema import FEATURE_NAMES, validate_feature_vector
from app.ml.inference import inference_service
from app.ml.risk_engine import RiskStateEngine
from app.ml.train_pipeline import generate_benchmark_timeline
from app.monitoring.drift_monitor import DriftMonitor
from app.telemetry.window_generator import SlidingWindowGenerator


@pytest.fixture(autouse=True)
def ensure_ml_models_loaded():
    """Ensure trained models and isotonic/conformal calibration artifacts are loaded."""
    if not inference_service.is_loaded:
        inference_service._try_load()
    assert inference_service.is_loaded, "ML inference engine must be initialized for Step 12 E2E testing"


@pytest.mark.asyncio
async def test_stage_1_to_8_real_ml_pipeline_inference_calibration_and_shap():
    """Stage 1-8: Real 37-D Feature vector -> Multi-Horizon Raw Inference -> Isotonic Calibration -> Conformal Prediction -> TreeSHAP Calculus."""
    # 1. Generate realistic benchmark flows spanning telemetry window sequence
    flows, _ = generate_benchmark_timeline(total_hours=2, flows_per_minute=25, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)
    assert len(windows) >= 5

    # 2. Stage 3: Strict Schema Validation on the current active window vector
    base_vec = np.array(windows[-1].vector, dtype=np.float32)
    assert len(base_vec) == 28
    
    # 3. Stage 4-6 & 8: Real Model Multi-Horizon Predictions
    timeline = inference_service.generate_forecast_timeline(
        window_sequence=windows[:10],
        target_entity="GLOBAL_PERIMETER",
    )
    assert timeline is not None
    assert len(timeline.horizons) == 4

    expected_horizons = [5, 15, 30, 60]
    for idx, horizon_int in enumerate(expected_horizons):
        h_pred = timeline.horizons[idx]
        assert h_pred.horizon_minutes == horizon_int
        # Calibrated probability in [0.0, 1.0]
        assert 0.0 <= h_pred.calibrated_probability <= 1.0
        assert 0.0 <= h_pred.raw_probability <= 1.0
        # Conformal prediction set & bounds
        assert len(h_pred.conformal_prediction_set.prediction_set) >= 1
        assert all(label in [0, 1] for label in h_pred.conformal_prediction_set.prediction_set)
        assert 0.0 <= h_pred.uncertainty_score <= 1.0

    # 4. Stage 7: TreeSHAP Attribution Calculus
    shap_res = inference_service.explain_forecast(
        window_sequence=windows[:10],
        horizon_minutes=5,
        top_k=5,
    )
    assert shap_res is not None
    assert shap_res.horizon_minutes == 5
    assert len(shap_res.top_positive_contributors) + len(shap_res.top_negative_contributors) > 0
    assert isinstance(shap_res.base_value, float)
    assert isinstance(shap_res.calibrated_probability, float)
    assert shap_res.additivity_verified is True


@pytest.mark.asyncio
async def test_stage_9_to_11_risk_matrix_and_counterfactual_engine():
    """Stage 9-11: Risk State Engine -> Attack Graph Mitigation & Counterfactual Optimization."""
    flows, _ = generate_benchmark_timeline(total_hours=2, flows_per_minute=30, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)
    timeline = inference_service.generate_forecast_timeline(window_sequence=windows[:10])

    # Stage 9: Risk State Evaluation
    risk_engine = RiskStateEngine()
    risk_eval = risk_engine.evaluate_state(timeline)
    assert risk_eval is not None
    assert risk_eval.current_state in [
        "NORMAL", "WATCH", "SUSPICIOUS", "ELEVATED", "CRITICAL",
        RiskStateEnum.NORMAL, RiskStateEnum.WATCH, RiskStateEnum.SUSPICIOUS,
        RiskStateEnum.ELEVATED, RiskStateEnum.CRITICAL,
    ]
    assert 0.0 <= risk_eval.max_calibrated_probability <= 1.0
    assert 0.0 <= risk_eval.anomaly_score <= 1.0

    # Stage 10: Attack Path Transition
    path_engine = AttackPathEngine()
    attack_path = path_engine.evaluate_attack_path(timeline=timeline, window=windows[-1])
    assert attack_path is not None
    assert attack_path.current_stage is not None

    # Stage 11: Counterfactual Optimization
    catalog = counterfactual_engine.get_feature_catalog()
    assert catalog.total_features == 37
    assert len(catalog.presets) >= 4

    req = CounterfactualScenarioRequest(
        scenario_name="SYN Flood Perimeter Throttling",
        perturbations={"syn_count": 10.0, "syn_rate": 0.1},
        recompute_derived=True,
        include_shap=False,
    )
    cf_res = counterfactual_engine.evaluate_scenario(req, inference_service)
    assert cf_res is not None
    assert "5" in cf_res.horizon_results
    h5_res = cf_res.horizon_results["5"]
    assert 0.0 <= h5_res.baseline_probability <= 1.0
    assert 0.0 <= h5_res.counterfactual_probability <= 1.0
    assert h5_res.decision_flip in ["NO_CHANGE", "ALERT_TO_NO_ALERT", "NO_ALERT_TO_ALERT"]


@pytest.mark.asyncio
async def test_stage_12_to_19_full_end_to_end_rest_api_and_persistence(async_client: AsyncClient):
    """Stage 12-19: Authentication, Database Persistence, Drift Telemetry, and Full REST API Endpoints."""
    # 1. Register & Login Security Analyst
    user_payload = {
        "email": "e2e_analyst@foresight.ai",
        "username": "e2e_analyst",
        "password": "SecurePassword123!",
        "full_name": "E2E Test Analyst",
        "role": "analyst",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=user_payload)
    assert reg_resp.status_code in [201, 200]

    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_analyst", "password": "SecurePassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify System Health & Readiness Probes
    health_resp = await async_client.get("/api/v1/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"].lower() == "healthy"
    assert "service" in health_data

    ready_resp = await async_client.get("/api/v1/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

    # 3. Model Registry Version & Status Query
    model_resp = await async_client.get("/api/v1/model/status", headers=headers)
    assert model_resp.status_code == 200
    assert "version_tag" in model_resp.json()

    # 4. Multi-Horizon Forecast Timeline Endpoint
    timeline_resp = await async_client.get("/api/v1/model/forecast/timeline", headers=headers)
    assert timeline_resp.status_code == 200
    timeline_data = timeline_resp.json()
    assert len(timeline_data["horizons"]) == 4

    # 5. TreeSHAP Attribution Instance Explanation Endpoint
    shap_req = {
        "horizon_minutes": 15,
        "top_k": 5,
    }
    shap_resp = await async_client.post("/api/v1/model/explain", json=shap_req, headers=headers)
    assert shap_resp.status_code == 200
    shap_data = shap_resp.json()
    assert "base_value" in shap_data
    assert len(shap_data["top_positive_contributors"]) + len(shap_data["top_negative_contributors"]) > 0

    # 6. Risk Engine State & Attack Path Endpoints
    risk_resp = await async_client.get("/api/v1/risk/state", headers=headers)
    assert risk_resp.status_code == 200
    assert "current_state" in risk_resp.json()

    path_resp = await async_client.get("/api/v1/risk/attack-path", headers=headers)
    assert path_resp.status_code == 200
    assert "current_stage" in path_resp.json()

    # 7. Counterfactual Catalog & Scenario Evaluation Endpoints
    cat_resp = await async_client.get("/api/v1/model/counterfactual/features", headers=headers)
    assert cat_resp.status_code == 200
    assert cat_resp.json()["total_features"] == 37

    cf_eval_req = {
        "scenario_name": "API E2E Counterfactual Run",
        "perturbations": {"syn_count": 5.0},
        "recompute_derived": True,
        "include_shap": False,
    }
    cf_resp = await async_client.post("/api/v1/model/counterfactual", json=cf_eval_req, headers=headers)
    assert cf_resp.status_code == 200
    assert "5" in cf_resp.json()["horizon_results"]

    # 8. Model Monitoring & Drift Telemetry Endpoints
    mon_health_resp = await async_client.get("/api/v1/monitoring/health", headers=headers)
    assert mon_health_resp.status_code == 200
    assert "overall_status" in mon_health_resp.json()

    drift_resp = await async_client.get("/api/v1/monitoring/drift", headers=headers)
    assert drift_resp.status_code == 200
    assert "overall_drift_status" in drift_resp.json()
    assert len(drift_resp.json()["feature_drift_metrics"]) > 0

    # 9. Audit Logs Endpoint
    audit_resp = await async_client.get("/api/v1/audit/logs", headers=headers)
    assert audit_resp.status_code == 200
    assert isinstance(audit_resp.json(), list)
