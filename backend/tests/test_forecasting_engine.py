"""Foresight AI - Comprehensive Automated Test Suite for AI Forecasting Brain (Step 3).

Tests:
1. Feature Dimension and Derivative Consistency (36 dense features)
2. Strict Chronological Splitting & Leakage Prevention (train < val < test ordering)
3. Multi-Horizon Future Target Alignment (5m, 15m, 30m, 60m bounds)
4. Unsupervised Anomaly Scoring (IsolationForest bounds [0.0, 1.0])
5. Platt Calibrator & Probability Boundedness
6. Multi-Horizon Forecasting Inference Service Execution
7. Lead-Time Evaluation Metric Engine
8. Forecast & Model Registry API Endpoints
"""

from datetime import datetime, timedelta, timezone
import os
import numpy as np
import pytest
from httpx import AsyncClient
from app.ml.anomaly_model import BehavioralAnomalyDetector
from app.ml.contracts import (
    FlowDirectionEnum,
    FlowRecord,
    ForecastResult,
    ProtocolEnum,
    TemporalWindowFeatures,
    ThreatSeverityEnum,
)
from app.ml.dataset_builder import ForecastingDatasetBuilder
from app.ml.inference import ForecastingInferenceService
from app.ml.lead_time import LeadTimeScoringEngine
from app.ml.trainer import ModelTrainer, PlattCalibrator
from app.telemetry.window_generator import SlidingWindowGenerator


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def synthetic_chronological_flows():
    """Generates 120 flows spanning 60 minutes with an attack burst at minute 40."""
    base_time = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    flows = []
    
    for i in range(120):
        t = base_time + timedelta(seconds=i * 30)
        # Normal flows
        packet_count = 50 + (i % 10)
        byte_count = packet_count * 200
        syn_count = 5
        rst_count = 0
        
        # Inject attack spike between 40m and 50m (i between 80 and 100)
        if 80 <= i <= 100:
            packet_count = 2500
            byte_count = 2500 * 64
            syn_count = 2400
            rst_count = 100

        flows.append(FlowRecord(
            flow_id=f"flow-{i:04d}",
            timestamp=t,
            source_ip="192.168.1.100" if i % 2 == 0 else f"10.0.0.{i % 20 + 1}",
            destination_ip="192.168.1.1",
            source_port=10000 + i,
            destination_port=80 if i % 2 == 0 else 443,
            protocol=ProtocolEnum.TCP,
            direction=FlowDirectionEnum.INGRESS,
            packet_count=packet_count,
            byte_count=byte_count,
            duration_ms=500.0,
            tcp_syn_count=syn_count,
            tcp_rst_count=rst_count,
            tcp_ack_count=10,
            tcp_fin_count=2,
            is_attack_ground_truth=(80 <= i <= 100),
            threat_label="Distributed Denial of Service" if (80 <= i <= 100) else "BENIGN",
        ))
    return flows


# ==============================================================================
# 1. TEMPORAL DATASET BUILDER & DERIVATIVE FEATURES
# ==============================================================================

def test_temporal_dataset_builder_features_and_derivatives(synthetic_chronological_flows):
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(synthetic_chronological_flows)
    
    assert len(windows) > 0
    builder = ForecastingDatasetBuilder(rolling_context_steps=4)
    
    ground_truth_events = [{
        "timestamp": datetime(2026, 9, 18, 12, 40, 0, tzinfo=timezone.utc),
        "threat_type": "Distributed Denial of Service",
        "severity": "CRITICAL",
        "duration_minutes": 10,
    }]
    
    dataset = builder.build_dataset_from_windows(windows, ground_truth_events)
    
    # Check dense feature dimensions: 28 Base + 8 Derivatives = 36 Features
    assert dataset.X.shape[1] == 36
    assert len(dataset.feature_names) == 36
    assert "packet_rate_slope" in dataset.feature_names
    assert "syn_rate_acceleration" in dataset.feature_names
    assert "entropy_change_dest_ports" in dataset.feature_names
    assert dataset.sample_count == len(windows)
    
    # Ensure no NaN or Inf in feature matrix
    assert not np.isnan(dataset.X).any()
    assert not np.isinf(dataset.X).any()


# ==============================================================================
# 2. STRICT CHRONOLOGICAL SPLITTING (ZERO TEMPORAL LEAKAGE)
# ==============================================================================

def test_zero_leakage_chronological_split(synthetic_chronological_flows):
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(synthetic_chronological_flows)
    
    builder = ForecastingDatasetBuilder()
    dataset = builder.build_dataset_from_windows(windows, [])
    
    train_set, val_set, test_set = builder.chronological_train_val_test_split(
        dataset, train_ratio=0.70, val_ratio=0.15
    )
    
    # 1. Verify split sums
    assert train_set.sample_count + val_set.sample_count + test_set.sample_count == dataset.sample_count
    
    # 2. Verify strict chronological partition order: max(train_t) <= min(val_t) <= max(val_t) <= min(test_t)
    train_max_t = max(train_set.timestamps)
    val_min_t = min(val_set.timestamps)
    val_max_t = max(val_set.timestamps)
    test_min_t = min(test_set.timestamps)
    
    assert train_max_t <= val_min_t, "Temporal leakage: Train timestamps overlap with Validation!"
    assert val_max_t <= test_min_t, "Temporal leakage: Validation timestamps overlap with Test!"


# ==============================================================================
# 3. FUTURE HORIZON TARGET ALIGNMENT
# ==============================================================================

def test_future_label_alignment_logic():
    base_t = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    
    # Attack scheduled from 10:15 to 10:30 (15m to 30m after base_t)
    ground_truth = [{
        "timestamp": base_t + timedelta(minutes=15),
        "threat_type": "SYN Flood",
        "severity": "HIGH",
        "duration_minutes": 15,
    }]
    
    builder = ForecastingDatasetBuilder()
    
    # Window 1: at t=10:00. Horizon 15m (10:15) should be True!
    w1 = TemporalWindowFeatures(
        window_id="win-001",
        window_start=base_t,
        window_end=base_t + timedelta(seconds=60),
        duration_seconds=60,
        flow_count=10,
        packet_count=100,
        byte_count=1000,
    )
    
    dataset = builder.build_dataset_from_windows([w1], ground_truth)
    
    # Check 15m horizon target: 15m is within [10:00 + 5m, 10:00 + 15m] -> True
    assert dataset.y_horizons[15][0] == 1, "15m target should be active"
    # Check 5m horizon target: [10:00, 10:05] -> Attack starts at 10:15, so 5m horizon is False (0)
    assert dataset.y_horizons[5][0] == 0, "5m target should be inactive at t=10:00"


# ==============================================================================
# 4. UNSUPERVISED ANOMALY MODEL
# ==============================================================================

def test_isolation_forest_anomaly_scoring():
    X_normal = np.random.normal(loc=10.0, scale=1.0, size=(100, 36))
    X_outlier = np.random.normal(loc=100.0, scale=10.0, size=(10, 36))
    
    model = BehavioralAnomalyDetector(contamination=0.05, random_state=42)
    model.fit(X_normal)
    
    scores_normal = model.score(X_normal)
    scores_outlier = model.score(X_outlier)
    
    # All scores must be strictly bounded in [0.0, 1.0]
    assert np.all(scores_normal >= 0.0) and np.all(scores_normal <= 1.0)
    assert np.all(scores_outlier >= 0.0) and np.all(scores_outlier <= 1.0)
    
    # Outliers should have higher mean anomaly score than normal samples
    assert np.mean(scores_outlier) > np.mean(scores_normal)


# ==============================================================================
# 5. PLATT CALIBRATOR
# ==============================================================================

def test_platt_calibrator_monotonicity_and_bounds():
    calibrator = PlattCalibrator()
    
    # Raw uncalibrated probabilities
    raw_probs = np.array([0.05, 0.15, 0.35, 0.65, 0.85, 0.95])
    y_true = np.array([0, 0, 0, 1, 1, 1])
    
    calibrator.fit(raw_probs, y_true)
    calibrated = calibrator.predict_proba(raw_probs)
    
    # Check bounds [0.0, 1.0]
    assert np.all(calibrated >= 0.0) and np.all(calibrated <= 1.0)
    
    # Check strictly monotonic increasing order
    assert np.all(np.diff(calibrated) >= 0.0)


# ==============================================================================
# 6. INFERENCE SERVICE MULTI-HORIZON PREDICTION
# ==============================================================================

def test_forecasting_inference_service(synthetic_chronological_flows):
    service = ForecastingInferenceService()
    
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(synthetic_chronological_flows)
    
    # Predict from sliding windows across all horizons
    results = service.predict_multi_horizon(windows[:10], target_entity="TEST_PERIMETER")
    
    assert len(results) == 4, "Must generate forecasts for all 4 horizons (5m, 15m, 30m, 60m)"
    
    horizons_returned = [r.forecast.horizon_minutes for r in results]
    assert horizons_returned == [5, 15, 30, 60]
    
    for r in results:
        assert isinstance(r, ForecastResult)
        assert 0.0 <= r.forecast.probability <= 1.0
        assert 0.0 <= r.forecast.confidence <= 1.0
        assert 0.0 <= r.anomaly_score <= 1.0
        assert r.uncertainty.credible_interval_lower <= r.uncertainty.credible_interval_upper
        assert r.model_version is not None
        assert len(r.feature_contributions) > 0


# ==============================================================================
# 7. LEAD-TIME METRIC SCORING ENGINE
# ==============================================================================

def test_lead_time_scoring_engine():
    engine = LeadTimeScoringEngine(probability_threshold=0.5)
    
    base_t = datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc)
    
    # Ground truth attack occurs at 14:15
    ground_truth = [{
        "id": "att-001",
        "timestamp": base_t + timedelta(minutes=15),
        "threat_type": "Distributed Denial of Service",
        "severity": "CRITICAL",
    }]
    
    # Forecast issued at 14:00 predicting attack with 15m horizon
    forecast = ForecastResult(
        id="fc-001",
        timestamp=base_t,
        forecast={
            "threat": "Distributed Denial of Service",
            "probability": 0.88,
            "confidence": 0.92,
            "horizon_minutes": 15,
            "severity": ThreatSeverityEnum.CRITICAL,
        },
        anomaly_score=0.75,
        uncertainty={
            "credible_interval_lower": 0.80,
            "credible_interval_upper": 0.95,
            "confidence_level": 0.95,
            "epistemic_uncertainty": 0.03,
            "aleatoric_uncertainty": 0.04,
        },
        model_version="v1.0.0-temporal-gbm",
        target_entity="GLOBAL_PERIMETER",
    )
    
    record = engine.match_forecast_to_attack(forecast, ground_truth)
    
    assert record.is_valid_early_warning is True
    assert record.actual_threat == "Distributed Denial of Service"
    # Lead time should be exactly 15 minutes
    assert record.lead_time_minutes == pytest.approx(15.0, abs=0.1)


# ==============================================================================
# 8. FORECAST & MODEL API ENDPOINTS
# ==============================================================================

@pytest.mark.asyncio
async def test_forecast_and_model_api_routes(async_client: AsyncClient):
    # 1. Test /api/v1/model/status
    res_status = await async_client.get("/api/v1/model/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert "version_tag" in data_status
    assert "supported_horizons" in data_status
    assert data_status["supported_horizons"] == [5, 15, 30, 60]

    # 2. Test /api/v1/model/calibration
    res_cal = await async_client.get("/api/v1/model/calibration")
    assert res_cal.status_code == 200
    data_cal = res_cal.json()
    assert "brier_score" in data_cal
    assert "expected_calibration_error" in data_cal
    assert "reliability_diagram_bins" in data_cal

    # 3. Test /api/v1/forecast/multi-horizon
    res_mh = await async_client.get("/api/v1/forecast/multi-horizon")
    assert res_mh.status_code == 200
    data_mh = res_mh.json()
    assert "target_entity" in data_mh
    assert "horizons" in data_mh
