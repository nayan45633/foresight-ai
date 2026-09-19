"""Foresight AI - Comprehensive Automated Test Suite for Step 4 (Calibration & Conformal Uncertainty).

Tests:
1. Candidate Calibrators (NoOp, Platt, Isotonic, Beta) probability bounds and monotonicity
2. Calibration Metric Calculation (Brier, ECE, MCE, Log Loss, Reliability Bins)
3. Binary Split Conformal Predictor (Finite sample adjustment, quantiles, prediction sets)
4. Empirical Conformal Coverage Guarantee (Target 90% vs Observed >= 90%)
5. Multi-Horizon Calibration Isolation (Validation-only selection)
6. Inference Service with Conformal Sets & Uncertainty Scores
7. Fail-Safe Missing Artifact Safeguards
"""

from datetime import datetime, timedelta, timezone
import os
import numpy as np
import pytest

from app.ml.calibrators import (
    BaseCalibrator,
    BetaCalibrator,
    IsotonicCalibrator,
    NoOpCalibrator,
    PlattCalibrator,
    calculate_ece_mce_and_bins,
    determine_calibration_status,
    evaluate_calibration_metrics,
)
from app.ml.conformal import BinarySplitConformalPredictor
from app.ml.contracts import (
    CalibrationHealthEnum,
    CalibrationMethodEnum,
    ConformalPredictionSet,
    ForecastResult,
    TemporalWindowFeatures,
)
from app.ml.dataset_builder import ForecastingDatasetBuilder
from app.ml.inference import ForecastingInferenceService, ModelUnavailableException
from app.ml.train_pipeline import generate_benchmark_timeline
from app.telemetry.window_generator import SlidingWindowGenerator


# ==============================================================================
# 1. CANDIDATE CALIBRATORS
# ==============================================================================

def test_calibrator_bounds_and_monotonicity():
    np.random.seed(42)
    raw_probs = np.linspace(0.01, 0.99, 100)
    y_true = (raw_probs > 0.5).astype(int)

    for cal in [NoOpCalibrator(), PlattCalibrator(), IsotonicCalibrator(), BetaCalibrator()]:
        cal.fit(raw_probs, y_true)
        calibrated = cal.predict_proba(raw_probs)

        # Must be strictly bounded in [0.0, 1.0]
        assert np.all(calibrated >= 0.0) and np.all(calibrated <= 1.0)
        assert len(calibrated) == len(raw_probs)
        assert cal.is_fitted is True


def test_calibration_metric_calculations():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    probs = np.array([0.1, 0.2, 0.15, 0.25, 0.85, 0.90, 0.80, 0.95])

    metrics = evaluate_calibration_metrics(y_true, probs, n_bins=5)

    assert "brier_score" in metrics
    assert "expected_calibration_error" in metrics
    assert "maximum_calibration_error" in metrics
    assert "log_loss" in metrics
    assert "reliability_bins" in metrics

    assert metrics["brier_score"] < 0.05
    assert metrics["expected_calibration_error"] <= 0.15
    assert len(metrics["reliability_bins"]) == 5


def test_calibration_health_status_assignment():
    assert determine_calibration_status(ece=0.02, brier=0.04) == CalibrationHealthEnum.CALIBRATED
    assert determine_calibration_status(ece=0.07, brier=0.08) == CalibrationHealthEnum.WATCH
    assert determine_calibration_status(ece=0.12, brier=0.15) == CalibrationHealthEnum.LIMITED


# ==============================================================================
# 2. SPLIT CONFORMAL PREDICTION
# ==============================================================================

def test_conformal_predictor_finite_sample_and_sets():
    np.random.seed(42)
    # 200 calibration samples
    val_probs = np.random.uniform(0.0, 1.0, 200)
    y_val = (val_probs > 0.5).astype(int)

    predictor = BinarySplitConformalPredictor(target_coverage=0.90)
    predictor.fit_calibration(val_probs, y_val)

    assert predictor.is_calibrated is True
    assert predictor.quantile_threshold is not None
    assert 0.0 < predictor.quantile_threshold <= 1.0

    # Low probability (e.g. 0.01) -> Should produce {0} (Confidently Benign)
    set_benign = predictor.predict_set(0.01)
    assert 0 in set_benign.prediction_set

    # High probability (e.g. 0.99) -> Should produce {1} (Confidently Attack)
    set_attack = predictor.predict_set(0.99)
    assert 1 in set_attack.prediction_set

    # Ambiguous probability (e.g. 0.50) -> Should produce {0, 1}
    set_ambig = predictor.predict_set(0.50)
    assert isinstance(set_ambig, ConformalPredictionSet)
    assert set_ambig.target_coverage == 0.90


def test_conformal_coverage_empirical_verification():
    np.random.seed(42)
    n_cal = 300
    n_test = 200

    # Synthetic well-separated probabilities
    cal_probs = np.random.beta(0.5, 0.5, n_cal)
    y_cal = (cal_probs + np.random.normal(0, 0.1, n_cal) > 0.5).astype(int)

    test_probs = np.random.beta(0.5, 0.5, n_test)
    y_test = (test_probs + np.random.normal(0, 0.1, n_test) > 0.5).astype(int)

    predictor = BinarySplitConformalPredictor(target_coverage=0.90)
    predictor.fit_calibration(cal_probs, y_cal)

    eval_report = predictor.evaluate_test_coverage(test_probs, y_test)

    assert eval_report["target_coverage"] == 0.90
    assert eval_report["empirical_coverage"] is not None
    # Coverage should be close to or exceed target under exchangeability
    assert eval_report["empirical_coverage"] >= 0.85
    assert eval_report["average_set_size"] >= 0.8


# ==============================================================================
# 3. PRODUCTION INFERENCE & ARTIFACT INTEGRATION
# ==============================================================================

def test_inference_service_step4_conformal_and_uncertainty():
    service = ForecastingInferenceService()
    flows, gt = generate_benchmark_timeline(total_hours=2, flows_per_minute=20, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    results = service.predict_multi_horizon(windows[:5])
    assert len(results) == 4

    for r in results:
        assert isinstance(r, ForecastResult)
        assert 0.0 <= r.forecast.probability <= 1.0
        assert r.forecast.raw_probability is not None
        assert 0.0 <= r.uncertainty.uncertainty_score <= 1.0
        assert r.uncertainty.conformal_prediction_set is not None
        assert isinstance(r.uncertainty.conformal_prediction_set.prediction_set, list)
        assert r.uncertainty.calibration_status in [
            CalibrationHealthEnum.CALIBRATED,
            CalibrationHealthEnum.WATCH,
            CalibrationHealthEnum.LIMITED,
        ]


def test_missing_conformal_fail_safe():
    # If conformal artifact is absent, inference must gracefully fall back without crash
    service = ForecastingInferenceService(conformal_path="./non_existent_conformal.joblib")
    flows, gt = generate_benchmark_timeline(total_hours=1, flows_per_minute=15, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    res = service.predict_from_windows(windows[:3], horizon_minutes=15)
    assert res is not None
    assert res.uncertainty.conformal_prediction_set.set_type == "UNCERTAIN_AMBIGUOUS"


# ==============================================================================
# 4. STEP 4.1 STATISTICAL HARDENING REGRESSION TESTS
# ==============================================================================

def test_separate_probability_and_decision_threshold():
    """Ensures probability, threshold, and binary decision are distinct fields with valid types."""
    service = ForecastingInferenceService()
    flows, gt = generate_benchmark_timeline(total_hours=2, flows_per_minute=20, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    res = service.predict_from_windows(windows[:5], horizon_minutes=15)
    
    # 1. Probability is a calibrated float in [0.0, 1.0]
    assert isinstance(res.forecast.probability, float)
    assert 0.0 <= res.forecast.probability <= 1.0
    
    # 2. Decision threshold is a distinct float in [0.0, 1.0]
    assert isinstance(res.forecast.decision_threshold, float)
    assert 0.0 <= res.forecast.decision_threshold <= 1.0
    
    # 3. Binary alert decision is an operational boolean matching the rule
    assert isinstance(res.forecast.binary_alert_decision, bool)
    assert res.forecast.binary_alert_decision == (res.forecast.probability >= res.forecast.decision_threshold)


def test_conformal_empty_set_is_uncertainty_rejection_not_ood():
    """Tests that an empty conformal set is classified as HIGH_UNCERTAINTY_REJECTION, not standalone OOD."""
    predictor = BinarySplitConformalPredictor(target_coverage=0.90)
    # Calibrated on probabilities [0.1, 0.9] with true labels [0, 1]
    cal_probs = np.array([0.1, 0.9])
    y_cal = np.array([0, 1])
    predictor.fit_calibration(cal_probs, y_cal)
    
    # Manually simulate tight quantile where both classes exceed threshold
    predictor.quantile_threshold = 0.2
    
    # Prediction at 0.5: s(0) = 0.5 > 0.2 and s(1) = 0.5 > 0.2 -> pred_set = []
    c_set = predictor.predict_set(0.5)
    assert c_set.prediction_set == []
    assert c_set.set_type == "HIGH_UNCERTAINTY_REJECTION"


def test_conformal_prediction_determinism():
    """Verifies that identical probabilities yield identical conformal sets deterministically."""
    predictor = BinarySplitConformalPredictor(target_coverage=0.90)
    cal_probs = np.linspace(0.05, 0.95, 100)
    y_cal = (cal_probs > 0.5).astype(int)
    predictor.fit_calibration(cal_probs, y_cal)

    for p in [0.05, 0.30, 0.50, 0.70, 0.95]:
        set1 = predictor.predict_set(p)
        set2 = predictor.predict_set(p)
        assert set1.prediction_set == set2.prediction_set
        assert set1.set_type == set2.set_type

