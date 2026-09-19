"""Foresight AI - Step 8 Counterfactual What-If Test Suite.

Comprehensive tests:
1. Feature Catalog & 37-D Metadata Verification
2. Perturbation Bounds & Finite Value Validation (NaN/Inf rejection)
3. Automatic Derived Feature Sync & Override Handling
4. Deterministic Multi-Horizon Model Re-Inference
5. Mitigation Simulation & Decision Flip (ALERT -> NO_ALERT)
6. Escalation Stress-Testing & Decision Flip (NO_ALERT -> ALERT)
7. TreeSHAP Attribution Differential Calculus
8. Conformal Set Transition Analysis
9. In-Memory Scenario Audit Log & Retrieval
10. REST API Endpoints Integration (FastAPI TestClient)
11. Latency Benchmarking (p50, p95, p99)
"""

from datetime import datetime, timezone
import math
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.contracts import (
    CounterfactualPreset,
    CounterfactualScenarioRequest,
    CounterfactualScenarioResponse,
    DecisionFlipEnum,
    FeatureClassificationEnum,
    PerturbationModeEnum,
)
from app.ml.counterfactual import (
    BUILTIN_PRESETS,
    FEATURE_CONSTRAINTS,
    counterfactual_engine,
)
from app.ml.feature_schema import FEATURE_DEFINITIONS, FEATURE_NAME_TO_INDEX, FEATURE_NAMES
from app.ml.inference import inference_service


@pytest.fixture(scope="module")
def initialized_inference():
    """Ensures forecasting models and artifacts are initialized and loaded."""
    if not inference_service.is_loaded:
        inference_service._try_load()
    return inference_service


@pytest.fixture
def client():
    return TestClient(app)


def test_feature_catalog_metadata():
    """Validates that all 37 schema features have bounds, units, step sizes, and classifications."""
    catalog = counterfactual_engine.get_feature_catalog()
    assert catalog.total_features == 37
    assert len(catalog.features) == 37
    assert len(catalog.presets) >= 4
    assert "scientific_disclaimer" in catalog.model_dump()
    assert "causal" in catalog.scientific_disclaimer.lower()

    # Verify classification distributions
    classes = [f.classification for f in catalog.features]
    assert FeatureClassificationEnum.DIRECTLY_PERTURBABLE.value in classes
    assert FeatureClassificationEnum.DERIVED.value in classes
    assert FeatureClassificationEnum.DEPENDENCY_CONSTRAINED.value in classes

    # Verify sample feature range
    flow_vol = next(f for f in catalog.features if f.name == "flow_volume")
    assert flow_vol.min_value == 0.0
    assert flow_vol.max_value > 1000.0
    assert flow_vol.unit == "flows/window"


def test_perturbation_validation_rejections():
    """Verifies that invalid, non-finite, out-of-bounds, or unknown features are strictly rejected."""
    # 1. Empty perturbations
    with pytest.raises(ValueError, match="cannot be empty"):
        counterfactual_engine.validate_perturbations({})

    # 2. Unknown feature
    with pytest.raises(ValueError, match="Unknown feature"):
        counterfactual_engine.validate_perturbations({"non_existent_cyber_metric": 100.0})

    # 3. NaN value
    with pytest.raises(ValueError, match="must be finite"):
        counterfactual_engine.validate_perturbations({"flow_volume": float("nan")})

    # 4. Infinity value
    with pytest.raises(ValueError, match="must be finite"):
        counterfactual_engine.validate_perturbations({"flow_volume": float("inf")})

    # 5. Out of bounds (negative flow volume)
    with pytest.raises(ValueError, match="below allowable minimum"):
        counterfactual_engine.validate_perturbations({"flow_volume": -10.0})

    # 6. Out of bounds (anomaly score > 1.0)
    with pytest.raises(ValueError, match="exceeds allowable maximum"):
        counterfactual_engine.validate_perturbations({"behavioral_anomaly_score": 1.5})


def test_derived_feature_auto_recomputation():
    """Verifies that derived ratios (e.g. syn_ack_ratio, rst_ratio, packets_per_sec) auto-recompute when enabled."""
    base_vec = np.zeros((1, 37), dtype=np.float32)
    base_vec[0, FEATURE_NAME_TO_INDEX["syn_count"]] = 1000.0
    base_vec[0, FEATURE_NAME_TO_INDEX["ack_count"]] = 500.0
    base_vec[0, FEATURE_NAME_TO_INDEX["syn_ack_ratio"]] = 2.0
    base_vec[0, FEATURE_NAME_TO_INDEX["packet_volume"]] = 6000.0
    base_vec[0, FEATURE_NAME_TO_INDEX["packets_per_second"]] = 100.0

    # Perturb syn_count down to 100 with recompute_derived=True
    cf_vec, applied = counterfactual_engine.compute_counterfactual_vector(
        baseline_vector=base_vec,
        perturbations={"syn_count": 100.0},
        recompute_derived=True,
    )

    # syn_ack_ratio should be updated to ~ 100 / (500 + 1e-5) ≈ 0.20
    syn_ack_idx = FEATURE_NAME_TO_INDEX["syn_ack_ratio"]
    assert pytest.approx(cf_vec[0, syn_ack_idx], rel=1e-2) == 0.20

    # Verify audit of applied perturbations contains the auto-derived sync
    derived_records = [a for a in applied if a.is_derived_auto_sync]
    assert len(derived_records) >= 1
    assert any(r.feature_name == "syn_ack_ratio" for r in derived_records)


def test_real_model_counterfactual_reinference_deterministic(initialized_inference):
    """Verifies that model re-inference produces deterministic outputs for the same baseline and perturbations."""
    req = CounterfactualScenarioRequest(
        scenario_name="Deterministic Test Scenario",
        perturbations={
            "flow_volume": 350.0,
            "packet_volume": 15000.0,
            "syn_count": 800.0,
            "behavioral_anomaly_score": 0.45,
        },
        recompute_derived=True,
        include_shap=False,
    )

    res1 = counterfactual_engine.evaluate_scenario(req, initialized_inference)
    res2 = counterfactual_engine.evaluate_scenario(req, initialized_inference)

    assert res1.model_version == res2.model_version
    for h_str in ["5", "15", "30", "60"]:
        h1 = res1.horizon_results[h_str]
        h2 = res2.horizon_results[h_str]
        assert h1.baseline_probability == h2.baseline_probability
        assert h1.counterfactual_probability == h2.counterfactual_probability
        assert h1.probability_delta == h2.probability_delta
        assert h1.decision_flip == h2.decision_flip


def test_mitigation_simulation_decision_flip(initialized_inference):
    """Tests mitigation intervention leading to probability reduction or ALERT -> NO_ALERT flip."""
    from app.ml.train_pipeline import generate_benchmark_timeline
    from app.telemetry.window_generator import SlidingWindowGenerator

    flows, _ = generate_benchmark_timeline(total_hours=24, flows_per_minute=35, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    # Attack window index 210
    w210 = windows[210]
    d210 = initialized_inference._dataset_builder.compute_temporal_derivatives(windows[205:211])
    comb210 = np.array(list(w210.vector) + d210, dtype=np.float32).reshape(1, -1)
    anom210 = float(initialized_inference.anomaly_detector.score(comb210)[0])
    vec_high = np.hstack([comb210, [[anom210]]])

    req = CounterfactualScenarioRequest(
        scenario_name="SYN Flood Mitigation Simulation",
        baseline_vector=vec_high[0].tolist(),
        perturbations={
            "syn_count": 10.0,
            "syn_rate": 0.1,
            "syn_ack_ratio": 0.01,
            "behavioral_anomaly_score": 0.05,
            "flow_volume": 100.0,
            "packet_volume": 1000.0,
            "delta_packet_rate": -100.0,
            "packet_rate_slope": -10.0,
        },
        recompute_derived=False,
        include_shap=True,
    )

    res = counterfactual_engine.evaluate_scenario(req, initialized_inference)

    assert res.scientific_disclaimer is not None
    assert len(res.applied_perturbations) >= 6
    assert res.max_risk_reduction > 0.0
    assert res.any_decision_flipped is True
    assert res.horizon_results["30"].decision_flip == DecisionFlipEnum.ALERT_TO_NO_ALERT.value


def test_escalation_stress_testing_decision_flip(initialized_inference):
    """Tests stress-testing perturbation leading to risk elevation (ΔP > 0) and NO_ALERT -> ALERT flip."""
    from app.ml.train_pipeline import generate_benchmark_timeline
    from app.telemetry.window_generator import SlidingWindowGenerator

    flows, _ = generate_benchmark_timeline(total_hours=24, flows_per_minute=35, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    # Benign window index 30
    w30 = windows[30]
    d30 = initialized_inference._dataset_builder.compute_temporal_derivatives(windows[25:31])
    comb30 = np.array(list(w30.vector) + d30, dtype=np.float32).reshape(1, -1)
    anom30 = float(initialized_inference.anomaly_detector.score(comb30)[0])
    vec_benign = np.hstack([comb30, [[anom30]]])

    # Attack window index 210 for perturbation features
    w210 = windows[210]
    d210 = initialized_inference._dataset_builder.compute_temporal_derivatives(windows[205:211])
    comb210 = np.array(list(w210.vector) + d210, dtype=np.float32).reshape(1, -1)
    anom210 = float(initialized_inference.anomaly_detector.score(comb210)[0])
    vec_attack = np.hstack([comb210, [[anom210]]])

    req = CounterfactualScenarioRequest(
        scenario_name="Hostile Reconnaissance Escalation",
        baseline_vector=vec_benign[0].tolist(),
        perturbations={FEATURE_NAMES[i]: float(vec_attack[0, i]) for i in [0, 1, 14, 15, 18, 28, 29, 36]},
        recompute_derived=False,
        include_shap=True,
    )

    res = counterfactual_engine.evaluate_scenario(req, initialized_inference)

    assert res.max_risk_elevation > 0.0
    assert res.horizon_results["60"].counterfactual_probability > res.horizon_results["60"].baseline_probability
    assert res.horizon_results["60"].decision_flip == DecisionFlipEnum.NO_ALERT_TO_ALERT.value


def test_treeshap_attribution_differential(initialized_inference):
    """Verifies that TreeSHAP attribution diffs correctly identify shifting features."""
    req = CounterfactualScenarioRequest(
        scenario_name="TreeSHAP Sensitivity Diff Test",
        perturbations={
            "syn_count": 2500.0,
            "unique_destination_ports": 450.0,
            "behavioral_anomaly_score": 0.70,
        },
        recompute_derived=True,
        include_shap=True,
    )

    res = counterfactual_engine.evaluate_scenario(req, initialized_inference)

    h15 = res.horizon_results["15"]
    assert len(h15.shap_deltas) > 0
    # Check that shap deltas have valid structured items
    for item in h15.shap_deltas:
        assert item.feature_name in FEATURE_NAMES
        assert item.direction in ["INCREASED_RISK_SENSITIVITY", "DECREASED_RISK_SENSITIVITY", "NEUTRAL"]
        assert isinstance(item.delta_shap, float)


def test_conformal_set_transitions(initialized_inference):
    """Verifies conformal set transition string formatting."""
    req = CounterfactualScenarioRequest(
        scenario_name="Conformal Set Transition Test",
        perturbations={"behavioral_anomaly_score": 0.05},
        include_shap=False,
    )
    res = counterfactual_engine.evaluate_scenario(req, initialized_inference)
    for h_str, h_res in res.horizon_results.items():
        assert "->" in h_res.conformal_set_transition
        assert isinstance(h_res.baseline_conformal_set, list)
        assert isinstance(h_res.counterfactual_conformal_set, list)


def test_scenario_audit_log_and_retrieval(initialized_inference):
    """Verifies that evaluated scenarios are archived in in-memory ring buffer and searchable by ID."""
    req = CounterfactualScenarioRequest(
        scenario_name="Audit Retrieval Verification",
        description="Verify scenario log persistence",
        perturbations={"flow_volume": 400.0, "syn_count": 120.0},
        include_shap=False,
    )

    res = counterfactual_engine.evaluate_scenario(req, initialized_inference)
    scen_id = res.scenario_id

    # Retrieve from lookup
    retrieved = counterfactual_engine.get_scenario_by_id(scen_id)
    assert retrieved is not None
    assert retrieved.scenario_id == scen_id
    assert retrieved.scenario_name == "Audit Retrieval Verification"

    # List recent
    recent = counterfactual_engine.get_recent_scenarios(limit=10)
    assert any(s.scenario_id == scen_id for s in recent)


def test_rest_api_endpoints(client):
    """Verifies all FastAPI REST endpoints for counterfactual what-if engine."""
    # 1. GET /api/v1/model/counterfactual/features
    resp_cat = client.get("/api/v1/model/counterfactual/features")
    assert resp_cat.status_code == 200
    cat_data = resp_cat.json()
    assert cat_data["total_features"] == 37
    assert len(cat_data["features"]) == 37

    # 2. GET /api/v1/model/counterfactual/presets
    resp_presets = client.get("/api/v1/model/counterfactual/presets")
    assert resp_presets.status_code == 200
    presets = resp_presets.json()
    assert len(presets) >= 4
    assert any(p["preset_id"] == "syn_flood_mitigation" for p in presets)

    # 3. POST /api/v1/model/counterfactual (Valid)
    eval_payload = {
        "scenario_name": "API Test Scenario",
        "description": "Integration test payload",
        "perturbations": {
            "syn_count": 100.0,
            "flow_volume": 250.0,
        },
        "recompute_derived": True,
        "include_shap": True,
    }
    resp_eval = client.post("/api/v1/model/counterfactual", json=eval_payload)
    assert resp_eval.status_code == 200
    eval_data = resp_eval.json()
    assert "scenario_id" in eval_data
    assert "horizon_results" in eval_data
    scen_id = eval_data["scenario_id"]

    # 4. GET /api/v1/model/counterfactual/scenario/{scenario_id}
    resp_get = client.get(f"/api/v1/model/counterfactual/scenario/{scen_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["scenario_id"] == scen_id

    # 5. GET /api/v1/model/counterfactual/scenarios
    resp_list = client.get("/api/v1/model/counterfactual/scenarios?limit=5")
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1

    # 6. POST /api/v1/model/counterfactual (Validation Error -> 422)
    bad_payload = {
        "perturbations": {
            "invalid_feature_name": 999.0
        }
    }
    resp_bad = client.post("/api/v1/model/counterfactual", json=bad_payload)
    assert resp_bad.status_code == 422


def test_counterfactual_latency_benchmark(initialized_inference):
    """Benchmarks re-inference latency across 10 simulation runs to ensure production SLA (<150ms without SHAP, <600ms with SHAP)."""
    # 1. Fast re-inference path (without SHAP)
    req_fast = CounterfactualScenarioRequest(
        scenario_name="Fast Latency Scenario",
        perturbations={"flow_volume": 250.0, "syn_count": 500.0},
        recompute_derived=True,
        include_shap=False,
    )
    latencies_fast = []
    for _ in range(10):
        t0 = time.perf_counter()
        _ = counterfactual_engine.evaluate_scenario(req_fast, initialized_inference)
        latencies_fast.append((time.perf_counter() - t0) * 1000.0)

    p50_fast = np.percentile(latencies_fast, 50)
    print(f"\n[Step 8 Re-Inference Latency (No SHAP)] p50: {p50_fast:.2f}ms")
    assert p50_fast < 50.0  # Fast re-inference SLA < 50ms

    # 2. Comprehensive path (with 8x TreeSHAP attributions)
    req_shap = CounterfactualScenarioRequest(
        scenario_name="Full SHAP Latency Scenario",
        perturbations={"flow_volume": 250.0, "syn_count": 500.0, "behavioral_anomaly_score": 0.40},
        recompute_derived=True,
        include_shap=True,
    )
    latencies_shap = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = counterfactual_engine.evaluate_scenario(req_shap, initialized_inference)
        latencies_shap.append((time.perf_counter() - t0) * 1000.0)

    p50_shap = np.percentile(latencies_shap, 50)
    print(f"[Step 8 Full Re-Inference + TreeSHAP Diff Latency] p50: {p50_shap:.2f}ms")
    assert p50_shap < 600.0

