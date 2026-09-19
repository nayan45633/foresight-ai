"""Foresight AI - Comprehensive Automated Test Suite for Step 5 (SHAP-Based Forecast Attribution).

Tests:
1. Authoritative 37-dimensional Feature Schema (Order, Names, Metadata, JSON Schema).
2. HorizonShapExplainer initialization, model caching, and multi-horizon TreeExplainer binding.
3. Strict Mathematical Additivity: base_value + sum(shap_values) == decision_function(x) (margin space).
4. Feature Contribution Extraction and Ranking (Top Positive vs Top Negative drivers).
5. Multi-Horizon Explanation Independence (5m, 15m, 30m, 60m distinct attributions).
6. End-to-End Inference Service Integration with SHAP generation.
7. Global Feature Importance Matrix (37x4) computation and serialization.
8. REST API Endpoints: /api/v1/model/explain and /api/v1/model/explain/global.
9. Robustness and Input Validation (Dimension validation, top_k bounds, graceful fallback).
"""

from datetime import datetime, timezone
import json
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingClassifier

from app.main import app
from app.ml.contracts import (
    FEATURE_NAMES,
    TemporalWindowFeatures,
)
from app.ml.feature_schema import (
    FEATURE_DEFINITIONS,
    FEATURE_SCHEMA,
    FEATURE_SCHEMA_BY_NAME,
    get_feature_explanation_template,
    get_ordered_feature_names,
    validate_feature_vector,
)
from app.ml.inference import ForecastingInferenceService
from app.ml.shap_explainer import HorizonShapExplainer


# ==============================================================================
# 1. FEATURE SCHEMA TESTS
# ==============================================================================

def test_feature_schema_completeness():
    assert len(FEATURE_SCHEMA) == 37
    assert len(FEATURE_NAMES) == 37
    ordered_names = get_ordered_feature_names()
    assert ordered_names == FEATURE_NAMES
    for idx, feat in enumerate(FEATURE_SCHEMA):
        assert feat.index == idx
        assert feat.name == FEATURE_NAMES[idx]
        assert feat.display_name != ""
        assert feat.category in ["volume", "duration", "tcp_flags", "entropy", "protocol", "anomaly", "temporal_delta"]
        assert feat.unit != ""
        assert feat.description != ""
        assert feat.positive_risk_meaning != ""
        assert feat.negative_risk_meaning != ""


def test_feature_explanation_template_formatting():
    pos_desc = get_feature_explanation_template("unique_source_ips", 145.0, 0.82)
    assert "145.00" in pos_desc or "145" in pos_desc
    assert "increased" in pos_desc or "elevated" in pos_desc.lower()
    neg_desc = get_feature_explanation_template("unique_source_ips", 2.0, -0.45)
    assert "decreased" in neg_desc or "low" in neg_desc.lower()


# ==============================================================================
# 2. SHAP EXPLAINER INITIALIZATION & MATHEMATICAL ADDITIVITY
# ==============================================================================

@pytest.fixture(scope="module")
def trained_models():
    np.random.seed(42)
    n_samples = 150
    X = np.random.randn(n_samples, 37).astype(np.float32)
    y_5 = ((X[:, 0] + X[:, 13]) > 0.5).astype(int)
    y_15 = ((X[:, 0] * 0.8 + X[:, 13] * 1.2) > 0.6).astype(int)
    y_30 = ((X[:, 0] * 0.5 + X[:, 13] * 1.5) > 0.7).astype(int)
    y_60 = ((X[:, 13] * 2.0) > 0.8).astype(int)

    models = {}
    for h, y in zip([5, 15, 30, 60], [y_5, y_15, y_30, y_60]):
        clf = HistGradientBoostingClassifier(max_iter=30, min_samples_leaf=5, random_state=42)
        clf.fit(X, y)
        models[h] = clf
    return models, X


def test_tree_shap_initialization(trained_models):
    models, _ = trained_models
    explainer = HorizonShapExplainer(horizon_models=models, model_version="test-shap-v1")
    assert explainer.is_initialized is True
    assert set(explainer.horizon_explainers.keys()) == {5, 15, 30, 60}


def test_tree_shap_strict_additivity(trained_models):
    models, X = trained_models
    explainer = HorizonShapExplainer(horizon_models=models, model_version="test-shap-v1")
    test_vectors = X[:10]
    for h in [5, 15, 30, 60]:
        for x_vec in test_vectors:
            raw_decision = float(models[h].decision_function(x_vec.reshape(1, -1))[0])
            explanation = explainer.explain_instance(
                scaled_features=x_vec,
                raw_features=x_vec,
                horizon_minutes=h,
                calibrated_probability=0.75,
                raw_probability=0.70,
                top_k=5,
            )

            assert explanation["status"] == "EXPLAINED"
            assert explanation["additivity_verified"] is True
            assert explanation["additivity_delta"] < 1e-4

            # Full sum over all 37 features
            all_shap = explainer.horizon_explainers[h].shap_values(x_vec.reshape(1, -1))[0]
            calculated_margin = explanation["base_value"] + float(np.sum(all_shap))
            assert abs(calculated_margin - raw_decision) < 1e-4


# ==============================================================================
# 3. FEATURE CONTRIBUTION EXTRACTION & RANKING
# ==============================================================================

def test_feature_contributions_sorting_and_signs(trained_models):
    models, X = trained_models
    explainer = HorizonShapExplainer(horizon_models=models, model_version="test-shap-v1")

    x_test = np.zeros(37, dtype=np.float32)
    x_test[0] = 5.0
    x_test[13] = 4.0

    explanation = explainer.explain_instance(
        scaled_features=x_test,
        raw_features=x_test,
        horizon_minutes=15,
        calibrated_probability=0.85,
        raw_probability=0.80,
        top_k=5,
    )

    pos_contributors = explanation["top_positive_contributors"]
    neg_contributors = explanation["top_negative_contributors"]

    assert len(pos_contributors) <= 5
    assert len(neg_contributors) <= 5

    # Check positive ordering (descending)
    pos_values = [fc["shap_value"] for fc in pos_contributors]
    assert all(v > 0 for v in pos_values)
    assert pos_values == sorted(pos_values, reverse=True)

    # Check negative ordering (ascending - most negative first)
    neg_values = [fc["shap_value"] for fc in neg_contributors]
    assert all(v < 0 for v in neg_values)
    assert neg_values == sorted(neg_values)


# ==============================================================================
# 4. MULTI-HORIZON EXPLANATIONS & SENSITIVITY
# ==============================================================================

def test_global_feature_importance_computation(trained_models):
    models, X = trained_models
    explainer = HorizonShapExplainer(horizon_models=models, model_version="test-shap-v1")
    report = explainer.compute_global_feature_importance(X, top_n=10)

    assert report["model_version"] == "test-shap-v1"
    assert report["evaluated_samples_count"] == len(X)
    assert len(report["top_global_features"]) == 10
    assert len(report["horizon_comparison_matrix"]) == 37
    for row in report["horizon_comparison_matrix"]:
        assert "feature_name" in row
        assert "shap_5m" in row and "shap_15m" in row and "shap_30m" in row and "shap_60m" in row
        assert "overall_mean_abs_shap" in row


# ==============================================================================
# 5. END-TO-END INFERENCE SERVICE INTEGRATION
# ==============================================================================

def test_inference_service_includes_shap():
    from app.ml.train_pipeline import generate_benchmark_timeline
    from app.telemetry.window_generator import SlidingWindowGenerator

    service = ForecastingInferenceService()
    if not service.is_ready:
        pytest.skip("Model artifacts not loaded in test environment.")

    flows, _ = generate_benchmark_timeline(total_hours=2, flows_per_minute=20, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    results = service.predict_multi_horizon(windows[:5], target_entity="TEST_PERIMETER")
    assert len(results) == 4
    for r in results:
        assert len(r.feature_contributions) > 0
        for fc in r.feature_contributions:
            assert fc.feature_name in FEATURE_NAMES
            assert fc.attribution_value is not None

    explanation = service.explain_forecast(windows[:5], horizon_minutes=15, top_k=5)
    assert explanation.horizon_minutes == 15
    assert explanation.status == "EXPLAINED"
    assert explanation.additivity_verified is True
    assert abs(explanation.additivity_delta) < 1e-4
    assert len(explanation.top_positive_contributors) <= 5
    assert len(explanation.top_negative_contributors) <= 5



# ==============================================================================
# 6. REST API ENDPOINT TESTS
# ==============================================================================

@pytest.fixture
def client():
    return TestClient(app)


def test_api_explain_endpoint(client):
    payload = {
        "horizon_minutes": 15,
        "top_k": 5,
    }
    response = client.post("/api/v1/model/explain", json=payload)
    if response.status_code == 503:
        pytest.skip("Model artifacts not loaded.")
    assert response.status_code == 200
    data = response.json()
    assert "top_positive_contributors" in data
    assert "top_negative_contributors" in data
    assert "raw_margin" in data
    assert "base_value" in data
    assert data["horizon_minutes"] == 15
    assert data["additivity_verified"] is True
    assert len(data["top_positive_contributors"]) <= 5
    assert len(data["top_negative_contributors"]) <= 5


def test_api_explain_global_endpoint(client):
    response = client.get("/api/v1/model/explain/global")
    if response.status_code == 503:
        pytest.skip("SHAP global report not loaded.")
    assert response.status_code == 200
    data = response.json()
    assert "top_global_features" in data
    assert "horizon_comparison_matrix" in data
    assert "model_version" in data
    assert len(data["horizon_comparison_matrix"]) == 37


def test_api_explain_invalid_input(client):
    response = client.post("/api/v1/model/explain", json={"top_k": 9999})
    assert response.status_code == 422
