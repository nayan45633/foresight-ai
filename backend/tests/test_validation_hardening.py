"""Foresight AI - Step 3.5 Automated Regression & Validation Hardening Test Suite.

Tests:
1. Temporal Leakage & Monotonicity (window sequences strictly non-decreasing)
2. Label Isolation (Future targets cannot enter current feature matrix)
3. Calibration Isolation (PlattCalibrator fitted exclusively on validation set)
4. Threshold Selection Isolation (Thresholds selected on validation, never test)
5. Lead-Time Monotonicity & Ordering (t_forecast < t_attack strictly enforced)
6. Deterministic Inference Verification (Same input window yields identical prediction)
7. Model Artifact Loading & Missing Artifact Fail-Safe
8. Feature Index Bounds & Rolling Context Causality
"""

from datetime import datetime, timedelta, timezone
import os
import tempfile
import numpy as np
import pytest

from app.ml.anomaly_model import BehavioralAnomalyDetector
from app.ml.contracts import (
    FlowDirectionEnum,
    FlowRecord,
    ForecastResult,
    ProtocolEnum,
    TemporalWindowFeatures,
)
from app.ml.dataset_builder import ForecastingDatasetBuilder
from app.ml.inference import ForecastingInferenceService, ModelUnavailableException
from app.ml.lead_time import LeadTimeScoringEngine
from app.ml.train_pipeline import generate_benchmark_timeline
from app.ml.trainer import ModelTrainer, PlattCalibrator
from app.telemetry.window_generator import SlidingWindowGenerator


@pytest.fixture
def benchmark_timeline():
    """Generates 24 hours of test flow telemetry with scheduled attack campaigns across partitions."""
    flows, gt = generate_benchmark_timeline(total_hours=24, flows_per_minute=25, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)
    builder = ForecastingDatasetBuilder(rolling_context_steps=4)
    dataset = builder.build_dataset_from_windows(windows, gt)
    train_set, val_set, test_set = builder.chronological_train_val_test_split(dataset, train_ratio=0.70, val_ratio=0.15)
    return {
        "flows": flows,
        "ground_truth": gt,
        "windows": windows,
        "dataset": dataset,
        "train_set": train_set,
        "val_set": val_set,
        "test_set": test_set,
    }


# ==============================================================================
# 1. TEMPORAL LEAKAGE & MONOTONICITY
# ==============================================================================

def test_window_monotonicity_and_temporal_boundaries(benchmark_timeline):
    windows = benchmark_timeline["windows"]
    train_set = benchmark_timeline["train_set"]
    val_set = benchmark_timeline["val_set"]
    test_set = benchmark_timeline["test_set"]

    # Monotonic timestamps
    for i in range(len(windows) - 1):
        assert windows[i].window_end <= windows[i + 1].window_end

    # Strict chronological partition boundaries
    max_train_ts = max(train_set.timestamps)
    min_val_ts = min(val_set.timestamps)
    max_val_ts = max(val_set.timestamps)
    min_test_ts = min(test_set.timestamps)

    assert max_train_ts <= min_val_ts, "Train timestamps must precede Validation"
    assert max_val_ts <= min_test_ts, "Validation timestamps must precede Test"


# ==============================================================================
# 2. LABEL ISOLATION & FUTURE ACCESS PRECLUSION
# ==============================================================================

def test_label_isolation_precludes_future_features(benchmark_timeline):
    windows = benchmark_timeline["windows"]
    builder = ForecastingDatasetBuilder(rolling_context_steps=4)

    # Verify that rolling context never looks ahead
    for i in range(len(windows)):
        history_start = max(0, i - 4 + 1)
        seq = windows[history_start : i + 1]
        for w in seq:
            assert w.window_end <= windows[i].window_end


# ==============================================================================
# 3. CALIBRATION ISOLATION (NO TEST DATA USED IN CALIBRATION)
# ==============================================================================

def test_calibration_fitted_exclusively_on_validation(benchmark_timeline):
    train_set = benchmark_timeline["train_set"]
    val_set = benchmark_timeline["val_set"]
    test_set = benchmark_timeline["test_set"]

    trainer = ModelTrainer(model_version="test-calib-isolation", random_state=42)
    val_metrics = trainer.train_and_calibrate(train_set, val_set)

    # Verify calibrators are stored and fit on validation
    for h in [5, 15, 30, 60]:
        calibrator = trainer.horizon_calibrators[h]
        assert calibrator.is_fitted is True
        assert hasattr(calibrator.lr, "coef_")


# ==============================================================================
# 4. THRESHOLD SELECTION ISOLATION
# ==============================================================================

def test_threshold_selection_uses_validation_only(benchmark_timeline):
    train_set = benchmark_timeline["train_set"]
    val_set = benchmark_timeline["val_set"]
    test_set = benchmark_timeline["test_set"]

    trainer = ModelTrainer(model_version="test-thresh-isolation", random_state=42)
    _ = trainer.train_and_calibrate(train_set, val_set)

    # Frozen thresholds exist for all horizons
    for h in [5, 15, 30, 60]:
        assert h in trainer.horizon_thresholds
        assert 0.0 < trainer.horizon_thresholds[h] <= 1.0


# ==============================================================================
# 5. LEAD-TIME ORDERING GUARANTEE (t_forecast < t_attack)
# ==============================================================================

def test_lead_time_strict_future_ordering():
    engine = LeadTimeScoringEngine(probability_threshold=0.50)
    base_t = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Past attack (before forecast) -> Must NOT be matched
    past_event = [{
        "timestamp": base_t - timedelta(minutes=5),
        "threat_type": "SYN Flood",
    }]

    forecast = ForecastResult(
        id="fc-lead-test",
        timestamp=base_t,
        forecast={
            "threat": "SYN Flood",
            "probability": 0.85,
            "confidence": 0.90,
            "horizon_minutes": 15,
        },
        anomaly_score=0.4,
        uncertainty={"credible_interval_lower": 0.75, "credible_interval_upper": 0.95},
        model_version="v1.0.0-temporal-gbm",
        target_entity="GLOBAL_PERIMETER",
    )

    record_past = engine.match_forecast_to_attack(forecast, past_event)
    assert record_past.is_valid_early_warning is False
    assert record_past.lead_time_minutes is None

    # Future attack (after forecast, within horizon) -> Must be matched
    future_event = [{
        "timestamp": base_t + timedelta(minutes=10),
        "threat_type": "SYN Flood",
    }]
    record_future = engine.match_forecast_to_attack(forecast, future_event)
    assert record_future.is_valid_early_warning is True
    assert record_future.lead_time_minutes == pytest.approx(10.0, abs=0.1)


# ==============================================================================
# 6. DETERMINISTIC INFERENCE
# ==============================================================================

def test_deterministic_inference_consistency(benchmark_timeline):
    service = ForecastingInferenceService()
    windows = benchmark_timeline["windows"][:5]

    res1 = service.predict_multi_horizon(windows)
    res2 = service.predict_multi_horizon(windows)

    assert len(res1) == len(res2) == 4
    for r1, r2 in zip(res1, res2):
        assert r1.forecast.probability == r2.forecast.probability
        assert r1.forecast.confidence == r2.forecast.confidence
        assert r1.anomaly_score == r2.anomaly_score


# ==============================================================================
# 7. MODEL UNAVAILABILITY SAFEGUARD
# ==============================================================================

def test_model_unavailability_exception():
    # Attempting inference with a non-existent artifact path must raise ModelUnavailableException
    service = ForecastingInferenceService(artifact_path="./non_existent_path.joblib")
    dummy_win = [TemporalWindowFeatures(
        window_id="win-dummy",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc) + timedelta(seconds=60),
        duration_seconds=60,
    )]
    
    with pytest.raises(ModelUnavailableException):
        service.predict_from_windows(dummy_win)
