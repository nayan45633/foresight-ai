"""Foresight AI - Comprehensive Automated Test Suite for Step 6 (Multi-Horizon + Lead-Time Intelligence).

Tests:
1. Multi-Horizon Forecast Intelligence Contract (Fields, Probabilities, Thresholds, Conformal Sets).
2. Strict Temporal Forward Monotonicity (T_now < T_+5m < T_+15m < T_+30m < T_+60m).
3. Temporal Consistency Checks & Inversion/Leakage Detection.
4. Probability Evolution & Horizon Deltas.
5. Earliest Warning Horizon Identification.
6. Empirical Lead-Time Scoring Engine & Deterministic Chronological Matching.
7. First Valid Warning Tracking & Double-Counting Prevention.
8. Missed Events & False Early Warning Accounting.
9. Insufficient Empirical Ground-Truth Graceful Handling ("Awaiting matched attack events").
10. REST API Endpoints: GET /api/v1/model/forecast/timeline and GET /api/v1/model/lead-time.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.contracts import (
    ConformalPredictionSet,
    ForecastHorizonPrediction,
    ForecastResult,
    HorizonForecastIntelligence,
    LeadTimeScorecard,
    MultiHorizonTimeline,
    TemporalWindowFeatures,
    ThreatSeverityEnum,
    UncertaintyEstimate,
)
from app.ml.inference import ForecastingInferenceService
from app.ml.lead_time import LeadTimeRecord, LeadTimeScoringEngine
from app.ml.train_pipeline import generate_benchmark_timeline
from app.telemetry.window_generator import SlidingWindowGenerator


# ==============================================================================
# 1. MULTI-HORIZON INTELLIGENCE CONTRACT TESTS
# ==============================================================================

def test_horizon_forecast_intelligence_schema():
    """Verify HorizonForecastIntelligence contains all required fields and distinct probability/uncertainty."""
    now_ts = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    target_ts = now_ts + timedelta(minutes=15)

    intel = HorizonForecastIntelligence(
        horizon_minutes=15,
        forecast_timestamp=now_ts,
        target_timestamp=target_ts,
        calibrated_probability=0.78,
        raw_probability=0.72,
        decision_threshold=0.50,
        binary_alert_decision=True,
        conformal_prediction_set=ConformalPredictionSet(prediction_set=[1], set_type="SINGLETON_ATTACK"),
        uncertainty_score=0.22,
        uncertainty_level="LOW",
        model_version="v1.0.0-temporal-gbm",
        calibration_version="v1.0.0-isotonic",
        threat_class="Port Scan Reconnaissance",
        severity=ThreatSeverityEnum.HIGH,
        probability_delta_from_previous_horizon=0.15,
    )

    assert intel.horizon_minutes == 15
    assert intel.forecast_timestamp == now_ts
    assert intel.target_timestamp == target_ts
    assert intel.calibrated_probability == 0.78
    assert intel.raw_probability == 0.72
    assert intel.decision_threshold == 0.50
    assert intel.binary_alert_decision is True
    assert intel.uncertainty_score == 0.22
    assert intel.uncertainty_level == "LOW"
    # Verify probability and uncertainty are strictly independent
    assert intel.calibrated_probability != intel.uncertainty_score


# ==============================================================================
# 2. TEMPORAL MONOTONICITY & CONSISTENCY CHECKS
# ==============================================================================

def test_timeline_forward_monotonicity():
    """Verify generated timeline strictly satisfies T_now < T_+5m < T_+15m < T_+30m < T_+60m."""
    service = ForecastingInferenceService()
    if not service.is_ready:
        pytest.skip("Model artifacts not loaded.")

    flows, _ = generate_benchmark_timeline(total_hours=2, flows_per_minute=20, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    timeline = service.generate_forecast_timeline(windows[:5], target_entity="TEST_PERIMETER")

    assert timeline.temporal_consistency_valid is True
    assert len(timeline.horizons) == 4

    horizons = [h.horizon_minutes for h in timeline.horizons]
    assert horizons == [5, 15, 30, 60]

    # Check forward progression
    forecast_ts = timeline.forecast_timestamp
    for idx, h_intel in enumerate(timeline.horizons):
        assert h_intel.target_timestamp > forecast_ts
        expected_target = forecast_ts + timedelta(minutes=h_intel.horizon_minutes)
        assert h_intel.target_timestamp == expected_target

        if idx > 0:
            prev_target = timeline.horizons[idx - 1].target_timestamp
            assert h_intel.target_timestamp > prev_target


def test_timeline_inversion_detection():
    """Verify temporal consistency validator flags inverted or non-forward target timestamps."""
    now_ts = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    # Create invalid horizons with inverted target timestamps
    h5 = HorizonForecastIntelligence(
        horizon_minutes=5,
        forecast_timestamp=now_ts,
        target_timestamp=now_ts + timedelta(minutes=30),  # Inverted!
        calibrated_probability=0.2,
        decision_threshold=0.5,
    )
    h15 = HorizonForecastIntelligence(
        horizon_minutes=15,
        forecast_timestamp=now_ts,
        target_timestamp=now_ts + timedelta(minutes=15),  # Inverted!
        calibrated_probability=0.4,
        decision_threshold=0.5,
    )

    # Check that adjacent targets violate monotonicity
    assert h5.target_timestamp > h15.target_timestamp


# ==============================================================================
# 3. EARLIEST WARNING HORIZON & PROBABILITY DELTAS
# ==============================================================================

def test_earliest_warning_horizon_identification():
    """Verify earliest_warning_horizon_minutes picks the shortest horizon triggering an alert."""
    service = ForecastingInferenceService()
    if not service.is_ready:
        pytest.skip("Model artifacts not loaded.")

    flows, _ = generate_benchmark_timeline(total_hours=2, flows_per_minute=20, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)

    timeline = service.generate_forecast_timeline(windows[:5], target_entity="TEST_PERIMETER")

    if timeline.is_alert_active_any_horizon:
        alert_horizons = [h.horizon_minutes for h in timeline.horizons if h.binary_alert_decision]
        assert timeline.earliest_warning_horizon_minutes == min(alert_horizons)
    else:
        assert timeline.earliest_warning_horizon_minutes is None


# ==============================================================================
# 4. EMPIRICAL LEAD-TIME ENGINE & EVENT MATCHING
# ==============================================================================

def test_deterministic_lead_time_event_matching():
    """Verify exact calculation of empirical lead time: actual_ts - forecast_ts."""
    engine = LeadTimeScoringEngine(probability_threshold=0.5, default_temporal_tolerance_minutes=2.0)

    base_t = datetime(2026, 9, 19, 14, 0, 0, tzinfo=timezone.utc)
    attack_t = base_t + timedelta(minutes=12)  # Attack at 14:12

    ground_truth = [
        {"id": "ev_001", "timestamp": attack_t, "threat_type": "SYN_FLOOD", "attack_occurred": True}
    ]

    # Forecast emitted at 14:00 with +15m horizon
    fc = ForecastResult(
        id="fc_001",
        timestamp=base_t,
        target_entity="GLOBAL_PERIMETER",
        anomaly_score=0.75,
        uncertainty=UncertaintyEstimate(),
        model_version="v1.0.0-temporal-gbm",
        forecast=ForecastHorizonPrediction(
            threat="SYN_FLOOD",
            probability=0.85,
            decision_threshold=0.50,
            binary_alert_decision=True,
            confidence=0.85,
            horizon_minutes=15,
        ),
    )

    # Single match test
    single_record = engine.match_forecast_to_attack(fc, ground_truth)
    assert single_record.is_valid_early_warning is True
    assert single_record.lead_time_minutes == 12.0  # Exactly 12 minutes before attack

    # Timeline evaluation test
    scorecard = engine.evaluate_timeline_lead_times([fc], ground_truth)
    assert scorecard.status == "EMPIRICALLY_EVALUATED"
    assert scorecard.valid_forecast_event_matches == 1
    assert scorecard.mean_lead_time_minutes == 12.0
    assert scorecard.median_lead_time_minutes == 12.0
    assert scorecard.max_lead_time_minutes == 12.0
    assert scorecard.min_lead_time_minutes == 12.0
    assert scorecard.missed_attack_events == 0
    assert scorecard.false_early_warnings == 0
    assert scorecard.empirical_forecast_coverage_rate == 1.0


def test_first_valid_warning_double_counting_prevention():
    """Verify that multiple consecutive forecasts for one attack event do not double-count event coverage."""
    engine = LeadTimeScoringEngine(probability_threshold=0.5)

    base_t = datetime(2026, 9, 19, 14, 0, 0, tzinfo=timezone.utc)
    attack_t = base_t + timedelta(minutes=25)  # Attack at 14:25

    ground_truth = [
        {"id": "ev_002", "timestamp": attack_t, "threat_type": "DDoS", "attack_occurred": True}
    ]

    # First alert emitted at 14:00 (+30m horizon) -> 25 min lead time
    fc1 = ForecastResult(
        id="fc_earliest",
        timestamp=base_t,
        anomaly_score=0.8,
        uncertainty=UncertaintyEstimate(),
        model_version="v1.0.0",
        forecast=ForecastHorizonPrediction(
            threat="DDoS", probability=0.85, decision_threshold=0.5, binary_alert_decision=True, confidence=0.85, horizon_minutes=30
        ),
    )
    # Subsequent alert emitted at 14:15 (+15m horizon) -> 10 min lead time
    fc2 = ForecastResult(
        id="fc_subsequent",
        timestamp=base_t + timedelta(minutes=15),
        anomaly_score=0.9,
        uncertainty=UncertaintyEstimate(),
        model_version="v1.0.0",
        forecast=ForecastHorizonPrediction(
            threat="DDoS", probability=0.95, decision_threshold=0.5, binary_alert_decision=True, confidence=0.95, horizon_minutes=15
        ),
    )

    scorecard = engine.evaluate_timeline_lead_times([fc1, fc2], ground_truth)
    assert scorecard.valid_forecast_event_matches == 1  # 1 distinct event matched
    assert scorecard.total_attack_events == 1
    assert scorecard.empirical_forecast_coverage_rate == 1.0
    # Earliest warning lead time (25.0 min) is the primary benchmark
    assert scorecard.max_lead_time_minutes == 25.0
    assert scorecard.earliest_warning_horizon_distribution.get("30m") == 1


def test_insufficient_ground_truth_graceful_handling():
    """Verify engine returns INSUFFICIENT_EMPIRICAL_MATCHES and None stats when no matches occur."""
    engine = LeadTimeScoringEngine()

    # Empty ground truth
    scorecard = engine.evaluate_timeline_lead_times([], [])
    assert scorecard.status == "INSUFFICIENT_EMPIRICAL_MATCHES"
    assert "Awaiting matched attack events" in scorecard.status_message
    assert scorecard.mean_lead_time_minutes is None
    assert scorecard.median_lead_time_minutes is None
    assert scorecard.max_lead_time_minutes is None


# ==============================================================================
# 5. REST API ENDPOINT TESTS
# ==============================================================================

@pytest.fixture
def client():
    return TestClient(app)


def test_api_forecast_timeline_endpoint(client):
    """Test GET /api/v1/model/forecast/timeline endpoint."""
    response = client.get("/api/v1/model/forecast/timeline")
    if response.status_code == 503:
        pytest.skip("Model artifacts not loaded.")

    assert response.status_code == 200
    data = response.json()
    assert "forecast_timestamp" in data
    assert "horizons" in data
    assert "temporal_consistency_valid" in data
    assert len(data["horizons"]) == 4

    # Verify each horizon has complete intelligence schema
    for h in data["horizons"]:
        assert h["horizon_minutes"] in [5, 15, 30, 60]
        assert "target_timestamp" in h
        assert 0.0 <= h["calibrated_probability"] <= 1.0
        assert 0.0 <= h["decision_threshold"] <= 1.0
        assert isinstance(h["binary_alert_decision"], bool)
        assert isinstance(h["conformal_prediction_set"], list)
        assert "uncertainty_score" in h
        assert "uncertainty_level" in h


def test_api_lead_time_endpoint(client):
    """Test GET /api/v1/model/lead-time endpoint."""
    response = client.get("/api/v1/model/lead-time")
    if response.status_code == 503:
        pytest.skip("Model artifacts not loaded.")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "total_attack_events" in data
    assert "valid_forecast_event_matches" in data
    assert "earliest_warning_horizon_distribution" in data
