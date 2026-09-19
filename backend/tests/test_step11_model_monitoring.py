"""Foresight AI - Step 11 Model Monitoring Subsystem Tests.

Tests:
- Data Quality Monitor (NaN/Inf, completeness, validity, status evaluation)
- Statistical Drift Monitor (PSI, KS statistic, insufficient data guards)
- Calibration Monitor (Brier, ECE, conformal coverage, awaiting ground truth)
- Multi-Horizon Forecast Performance Monitor (+5m, +15m, +30m, +60m isolation)
- Composite Model Health Evaluator
- Monitoring API endpoints
"""

import numpy as np
import pytest
from httpx import AsyncClient

from app.monitoring.calibration_monitor import CalibrationHealthStatus, CalibrationMonitor
from app.monitoring.data_quality_monitor import DataQualityMonitor, MonitoringStatus
from app.monitoring.drift_monitor import DriftMonitor, DriftStatus
from app.monitoring.forecast_monitor import ForecastPerformanceMonitor, PerformanceStatus
from app.monitoring.model_health import CompositeHealthStatus, ModelHealthEvaluator


def test_data_quality_evaluation():
    """Verifies that DataQualityMonitor detects NaNs, invalid dimensions, and computes completeness accurately."""
    monitor = DataQualityMonitor(expected_feature_count=37)

    # 1. Clean feature matrix (100 samples x 37 features)
    clean_mat = np.random.uniform(0.0, 10.0, (100, 37)).astype(np.float32)
    report_clean = monitor.evaluate_batch(clean_mat)
    assert report_clean.overall_status == MonitoringStatus.HEALTHY
    assert report_clean.completeness_score == 1.0
    assert report_clean.validity_score == 1.0
    assert len(report_clean.feature_metrics) == 37

    # 2. Corrupt matrix with NaNs
    corrupt_mat = clean_mat.copy()
    corrupt_mat[:20, 0] = np.nan
    report_corrupt = monitor.evaluate_batch(corrupt_mat)
    assert report_corrupt.completeness_score < 1.0
    assert report_corrupt.feature_metrics[0].nan_count == 20

    # 3. Wrong column count (Critical status)
    wrong_dim_mat = np.random.uniform(0.0, 10.0, (50, 20)).astype(np.float32)
    report_dim = monitor.evaluate_batch(wrong_dim_mat)
    assert report_dim.overall_status == MonitoringStatus.CRITICAL


def test_drift_monitor_psi_and_insufficient_data():
    """Verifies PSI calculation, KS statistic, and insufficient data guards."""
    monitor = DriftMonitor()

    # 1. Insufficient sample size guard (< 30 samples)
    small_base = np.random.normal(0, 1, 20)
    small_curr = np.random.normal(0, 1, 20)
    res_insufficient = monitor.evaluate_feature_drift(
        baseline_matrix=small_base.reshape(-1, 1),
        current_matrix=small_curr.reshape(-1, 1),
    )
    assert res_insufficient.overall_drift_status == DriftStatus.INSUFFICIENT_DATA

    # 2. Stable distributions (N = 500 samples)
    np.random.seed(42)
    base_dist = np.random.normal(5.0, 1.0, 500)
    curr_dist_stable = base_dist.copy() + np.random.normal(0, 0.01, 500)
    psi_stable = monitor.compute_psi(base_dist, curr_dist_stable)
    ks_stable = monitor.compute_ks_statistic(base_dist, curr_dist_stable)
    assert psi_stable < 0.05  # Negligible drift
    assert ks_stable < 0.10

    # 3. Significant drift distribution
    curr_dist_shifted = np.random.normal(8.0, 2.5, 500)
    psi_shifted = monitor.compute_psi(base_dist, curr_dist_shifted)
    assert psi_shifted >= 0.25  # Significant drift


def test_calibration_monitor_with_and_without_ground_truth():
    """Verifies calibration monitoring returns AWAITING GROUND TRUTH when labels are missing and computes ECE when provided."""
    cal_monitor = CalibrationMonitor(num_bins=10, target_coverage=0.90)

    # 1. Without ground truth -> Awaiting ground truth
    preds = np.array([0.1, 0.4, 0.8, 0.9])
    res_no_gt = cal_monitor.evaluate_calibration(preds, ground_truth_labels=None, horizon_minutes=15)
    assert res_no_gt.status == CalibrationHealthStatus.AWAITING_GROUND_TRUTH

    # 2. With ground truth -> Calculates Brier and ECE
    np.random.seed(42)
    y_prob = np.random.uniform(0.1, 0.9, 300)
    y_true = (np.random.uniform(0.0, 1.0, 300) < y_prob).astype(int)
    res_with_gt = cal_monitor.evaluate_calibration(y_prob, y_true, horizon_minutes=15)
    assert res_with_gt.status in [CalibrationHealthStatus.CALIBRATED, CalibrationHealthStatus.WATCH]
    assert res_with_gt.brier_score is not None
    assert res_with_gt.expected_calibration_error is not None
    assert len(res_with_gt.reliability_bins) == 10


def test_forecast_performance_monitor_sample_guards():
    """Verifies that performance monitor requires at least 5 attack events before computing F1/Precision."""
    perf_monitor = ForecastPerformanceMonitor()

    # 1. 2 attack events (Insufficient empirical evidence)
    y_prob = np.array([0.8, 0.9, 0.1, 0.2, 0.3, 0.1])
    y_true = np.array([1, 1, 0, 0, 0, 0])
    res_low = perf_monitor.evaluate_horizon(y_prob, y_true, horizon_minutes=15)
    assert res_low.status == PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE

    # 2. 10 attack events -> Evaluates metrics
    np.random.seed(42)
    y_true_10 = np.array([1] * 10 + [0] * 40)
    y_prob_10 = np.array([0.85] * 10 + [0.15] * 40)
    res_10 = perf_monitor.evaluate_horizon(y_prob_10, y_true_10, horizon_minutes=15)
    assert res_10.status == PerformanceStatus.OPTIMAL
    assert res_10.f1_score == 1.0
    assert res_10.precision == 1.0
    assert res_10.recall == 1.0


def test_composite_model_health_logic():
    """Verifies composite model health decision tree."""
    evaluator = ModelHealthEvaluator()

    # Healthy scenario
    healthy_report = evaluator.evaluate(
        model_version="production-v1",
        artifact_integrity={"status": "VERIFIED", "is_tamper_free": True},
        data_quality_status=MonitoringStatus.HEALTHY,
        drift_status="STABLE",
        calibration_status="CALIBRATED",
        performance_status="OPTIMAL",
    )
    assert healthy_report.overall_status == CompositeHealthStatus.HEALTHY

    # Tampered artifact -> Critical
    tampered_report = evaluator.evaluate(
        model_version="production-v1",
        artifact_integrity={"status": "DEGRADED", "is_tamper_free": False},
        data_quality_status=MonitoringStatus.HEALTHY,
        drift_status="STABLE",
        calibration_status="CALIBRATED",
        performance_status="OPTIMAL",
    )
    assert tampered_report.overall_status == CompositeHealthStatus.CRITICAL


@pytest.mark.asyncio
async def test_monitoring_api_endpoints(async_client: AsyncClient):
    """Verifies that all monitoring endpoints return valid schemas and HTTP 200."""
    # 1. Model Health
    res_health = await async_client.get("/api/v1/monitoring/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert "overall_status" in data_health
    assert "signals" in data_health

    # 2. Data Quality
    res_dq = await async_client.get("/api/v1/monitoring/data-quality")
    assert res_dq.status_code == 200
    data_dq = res_dq.json()
    assert "completeness_score" in data_dq
    assert "validity_score" in data_dq

    # 3. Drift
    res_drift = await async_client.get("/api/v1/monitoring/drift")
    assert res_drift.status_code == 200
    data_drift = res_drift.json()
    assert "overall_drift_status" in data_drift

    # 4. Calibration
    res_cal = await async_client.get("/api/v1/monitoring/calibration")
    assert res_cal.status_code == 200
    data_cal = res_cal.json()
    assert "overall_status" in data_cal

    # 5. Performance
    res_perf = await async_client.get("/api/v1/monitoring/performance")
    assert res_perf.status_code == 200
    data_perf = res_perf.json()
    assert "overall_status" in data_perf

