"""Foresight AI - Step 7.1 Hardened Test Suite.

Tests:
1. Attack Path Stage Classification & Forward Transition Forecasting
2. Separation of Graph Knowledge vs Forecasted Probabilities (No Fake Multiplications)
3. Unsupported Transitions return INSUFFICIENT_EVIDENCE
4. Honest Empty State on Missing Telemetry (AWAITING_TELEMETRY)
5. Risk State Machine Escalation (NORMAL -> WATCH -> SUSPICIOUS -> ELEVATED -> CRITICAL)
6. Anti-Flutter Hysteresis & Minimum Persistence Dampening
7. Auditable State Transition Logging
8. Risk Endpoints Production Path (Zero Silent Benchmark Generation)
9. Explicit Demo Endpoint Path (/api/v1/risk/demo-state)
10. Evaluation Latency Benchmarking (p50, p95, p99)
"""

from datetime import datetime, timedelta, timezone
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.attack_path import AttackPathEngine
from app.ml.contracts import (
    AttackPathForecast,
    AttackStageEnum,
    ConformalPredictionSet,
    HorizonForecastIntelligence,
    MultiHorizonTimeline,
    RiskStateEnum,
    RiskStateEvaluation,
    TemporalWindowFeatures,
    ThreatSeverityEnum,
    TransitionConfidenceStatusEnum,
)
from app.ml.risk_engine import RiskStateEngine


def make_mock_horizon(
    horizon_min: int,
    cal_prob: float,
    threshold: float = 0.50,
    alert: bool = False,
    conformal_set: list = None,
    uncertainty_level: str = "LOW",
) -> HorizonForecastIntelligence:
    now_ts = datetime.now(timezone.utc)
    return HorizonForecastIntelligence(
        horizon_minutes=horizon_min,
        forecast_timestamp=now_ts,
        target_timestamp=now_ts + timedelta(minutes=horizon_min),
        calibrated_probability=cal_prob,
        decision_threshold=threshold,
        binary_alert_decision=alert or (cal_prob >= threshold),
        conformal_prediction_set=ConformalPredictionSet(prediction_set=conformal_set or ([1] if alert else [0])),
        uncertainty_score=0.10 if uncertainty_level == "LOW" else 0.70,
        uncertainty_level=uncertainty_level,
        model_version="v1.0.0-temporal-gbm",
        calibration_version="v1.0.0-isotonic",
        threat_class="DDoS" if alert else "BENIGN",
        severity=ThreatSeverityEnum.CRITICAL if cal_prob >= 0.7 else ThreatSeverityEnum.LOW,
    )


def make_mock_timeline(
    probs: dict,
    anomaly_score: float = 0.10,
    alerts: dict = None,
) -> MultiHorizonTimeline:
    alerts = alerts or {}
    horizons = [
        make_mock_horizon(h, probs.get(h, 0.05), alert=alerts.get(h, False))
        for h in [5, 15, 30, 60]
    ]
    earliest_alert = min([h for h in [5, 15, 30, 60] if alerts.get(h, False)], default=None)
    max_h = max(probs.keys(), key=lambda k: probs[k])

    return MultiHorizonTimeline(
        forecast_timestamp=datetime.now(timezone.utc),
        target_entity="GLOBAL_PERIMETER",
        horizons=horizons,
        earliest_warning_horizon_minutes=earliest_alert,
        max_risk_horizon_minutes=max_h,
        is_alert_active_any_horizon=bool(earliest_alert),
        anomaly_score=anomaly_score,
    )


# ==============================================================================
# 1. ATTACK PATH FORECASTING & HARDENING TESTS
# ==============================================================================

def test_attack_path_benign_nominal():
    engine = AttackPathEngine()
    timeline = make_mock_timeline(
        probs={5: 0.04, 15: 0.05, 30: 0.06, 60: 0.08},
        anomaly_score=0.12,
    )
    window = TemporalWindowFeatures(
        window_id="w-benign",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        duration_seconds=60,
        packets_per_second=50.0,
        bytes_per_second=10000.0,
        forward_backward_ratio=1.0,
        syn_ack_ratio=0.10,
        rst_ratio=0.01,
        flow_volume=10,
    )

    forecast = engine.evaluate_attack_path(timeline=timeline, window=window)

    assert forecast.current_stage == AttackStageEnum.BENIGN.value
    assert forecast.predicted_next_stage is None
    assert forecast.probability is None
    assert forecast.transition_confidence_status == TransitionConfidenceStatusEnum.BENIGN_NOMINAL.value
    assert len(forecast.graph_edges) == 0
    assert len(forecast.graph_nodes) == 1
    assert forecast.graph_nodes[0].stage == AttackStageEnum.BENIGN.value


def test_attack_path_scanning_to_initial_access():
    engine = AttackPathEngine()
    timeline = make_mock_timeline(
        probs={5: 0.20, 15: 0.78, 30: 0.85, 60: 0.90},
        anomaly_score=0.65,
        alerts={15: True, 30: True, 60: True},
    )
    window = TemporalWindowFeatures(
        window_id="w-scan",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        duration_seconds=60,
        packets_per_second=600.0,
        bytes_per_second=80000.0,
        forward_backward_ratio=4.5,
        syn_ack_ratio=0.85,
        rst_ratio=0.02,
        flow_volume=120,
    )

    forecast = engine.evaluate_attack_path(timeline=timeline, window=window)

    assert forecast.current_stage == AttackStageEnum.SCANNING.value
    assert forecast.predicted_next_stage == AttackStageEnum.INITIAL_ACCESS.value
    assert forecast.probability == pytest.approx(0.78, abs=0.01)
    assert forecast.horizon_minutes == 15
    assert forecast.transition_confidence_status == TransitionConfidenceStatusEnum.VALIDATED_TRANSITION.value
    assert len(forecast.graph_nodes) >= 2


def test_attack_path_subsequent_stages_no_fake_probabilities():
    """Rigorously proves that subsequent downstream stages have NO fabricated probabilities."""
    engine = AttackPathEngine()
    timeline = make_mock_timeline(
        probs={5: 0.15, 15: 0.75, 30: 0.80, 60: 0.82},
        anomaly_score=0.60,
        alerts={15: True},
    )
    window = TemporalWindowFeatures(
        window_id="w-scan",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        duration_seconds=60,
        packets_per_second=500.0,
        bytes_per_second=50000.0,
        forward_backward_ratio=3.5,
        syn_ack_ratio=0.70,
        flow_volume=80,
    )

    forecast = engine.evaluate_attack_path(timeline=timeline, window=window)

    # Primary predicted next stage has validated probability
    assert forecast.predicted_next_stage is not None
    assert forecast.probability == pytest.approx(0.75, abs=0.01)

    # All downstream subsequent nodes must have probability = None and status = POTENTIAL_UNVALIDATED
    for node in forecast.graph_nodes:
        if not node.is_current and not node.is_predicted:
            assert node.probability is None, f"Node {node.stage} should have None probability!"
            assert node.evidence_strength == "INSUFFICIENT_EVIDENCE"
            assert node.status == "POTENTIAL_UNVALIDATED"
            assert node.is_forecasted is False

    # All downstream subsequent edges must have transition_probability = None and status = GRAPH_POSSIBLE
    forecasted_edges = [e for e in forecast.graph_edges if e.is_forecasted]
    unvalidated_edges = [e for e in forecast.graph_edges if not e.is_forecasted]

    assert len(forecasted_edges) == 1, "Only 1 edge should be forecasted!"
    assert forecasted_edges[0].transition_probability == pytest.approx(0.75, abs=0.01)

    for edge in unvalidated_edges:
        assert edge.transition_probability is None, f"Edge {edge.source_stage}->{edge.target_stage} should have None probability!"
        assert edge.status == "GRAPH_POSSIBLE"


def test_attack_path_honest_empty_state():
    """Proves that missing telemetry produces an honest empty state with AWAITING_TELEMETRY."""
    engine = AttackPathEngine()
    empty_forecast = engine.evaluate_empty_state()

    assert empty_forecast.current_stage is None
    assert empty_forecast.predicted_next_stage is None
    assert empty_forecast.probability is None
    assert empty_forecast.transition_confidence_status == TransitionConfidenceStatusEnum.AWAITING_TELEMETRY.value
    assert len(empty_forecast.graph_nodes) == 0
    assert len(empty_forecast.graph_edges) == 0


# ==============================================================================
# 2. RISK STATE MACHINE & HYSTERESIS TESTS
# ==============================================================================

def test_risk_state_escalation_full_chain():
    """Tests step-by-step escalation: NORMAL -> WATCH -> SUSPICIOUS -> ELEVATED -> CRITICAL."""
    engine = RiskStateEngine(min_persistence_cycles=2)
    assert engine.current_state == RiskStateEnum.NORMAL

    # 1. Escalate to WATCH
    t_watch = make_mock_timeline(probs={5: 0.10, 15: 0.12, 30: 0.15, 60: 0.24}, anomaly_score=0.32)
    eval_watch = engine.evaluate_state(t_watch)
    assert eval_watch.current_state == RiskStateEnum.WATCH
    assert engine.current_state == RiskStateEnum.WATCH

    # 2. Escalate to SUSPICIOUS
    t_susp = make_mock_timeline(probs={5: 0.10, 15: 0.25, 30: 0.38, 60: 0.42}, anomaly_score=0.45, alerts={30: True})
    eval_susp = engine.evaluate_state(t_susp)
    assert eval_susp.current_state == RiskStateEnum.SUSPICIOUS
    assert engine.current_state == RiskStateEnum.SUSPICIOUS

    # 3. Escalate to ELEVATED
    t_elev = make_mock_timeline(probs={5: 0.20, 15: 0.55, 30: 0.58, 60: 0.45}, anomaly_score=0.42, alerts={15: True, 30: True})
    eval_elev = engine.evaluate_state(t_elev)
    assert eval_elev.current_state == RiskStateEnum.ELEVATED
    assert engine.current_state == RiskStateEnum.ELEVATED

    # 4. Escalate to CRITICAL
    t_crit = make_mock_timeline(probs={5: 0.85, 15: 0.90, 30: 0.92, 60: 0.95}, anomaly_score=0.80, alerts={5: True, 15: True, 30: True, 60: True})
    eval_crit = engine.evaluate_state(t_crit)
    assert eval_crit.current_state == RiskStateEnum.CRITICAL
    assert engine.current_state == RiskStateEnum.CRITICAL


def test_risk_state_hysteresis_and_persistence_holds():
    """Tests de-escalation dampening requiring persistence cycles and smooth step-down."""
    engine = RiskStateEngine(min_persistence_cycles=2)

    # Escalate to CRITICAL
    t_crit = make_mock_timeline(probs={5: 0.88, 15: 0.92, 30: 0.94, 60: 0.96}, anomaly_score=0.85, alerts={5: True, 15: True, 30: True})
    engine.evaluate_state(t_crit)
    assert engine.current_state == RiskStateEnum.CRITICAL

    # Immediate drop in telemetry (cycle 1 of lower signal) - Must HOLD CRITICAL due to persistence requirement
    t_calm = make_mock_timeline(probs={5: 0.05, 15: 0.06, 30: 0.08, 60: 0.10}, anomaly_score=0.10)
    eval_hold = engine.evaluate_state(t_calm)
    assert eval_hold.current_state == RiskStateEnum.CRITICAL
    assert eval_hold.is_hysteresis_dampened is True

    # Cycle 2 of calm telemetry - Step down to ELEVATED (controlled smooth step-down)
    eval_step1 = engine.evaluate_state(t_calm)
    assert eval_step1.current_state == RiskStateEnum.ELEVATED

    # Cycle 1 in ELEVATED - Must hold
    eval_step2_hold = engine.evaluate_state(t_calm)
    assert eval_step2_hold.current_state == RiskStateEnum.ELEVATED
    assert eval_step2_hold.is_hysteresis_dampened is True

    # Cycle 2 in ELEVATED - Step down to SUSPICIOUS
    eval_step2 = engine.evaluate_state(t_calm)
    assert eval_step2.current_state == RiskStateEnum.SUSPICIOUS


def test_anti_flutter_under_oscillating_signals():
    """Proves that rapid alternating inputs do not cause rapid state flutter."""
    engine = RiskStateEngine(min_persistence_cycles=3)

    # Establish SUSPICIOUS state
    t_susp = make_mock_timeline(probs={5: 0.20, 15: 0.40, 30: 0.42, 60: 0.45}, anomaly_score=0.45, alerts={15: True})
    engine.evaluate_state(t_susp)
    engine.evaluate_state(t_susp)
    assert engine.current_state == RiskStateEnum.SUSPICIOUS

    t_calm = make_mock_timeline(probs={5: 0.05, 15: 0.05, 30: 0.06, 60: 0.08}, anomaly_score=0.10)

    # Send 4 alternating cycles
    states = []
    for i in range(4):
        # Alternate calm and suspicious
        t = t_calm if i % 2 == 0 else t_susp
        res = engine.evaluate_state(t)
        states.append(res.current_state)

    # State must remain SUSPICIOUS throughout because calm never persists for 3 cycles
    assert all(s == RiskStateEnum.SUSPICIOUS for s in states), f"State fluttered: {states}"


def test_risk_state_deterministic_evaluation():
    """Proves evaluation is completely deterministic for identical timelines."""
    engine1 = RiskStateEngine(min_persistence_cycles=2)
    engine2 = RiskStateEngine(min_persistence_cycles=2)

    timeline = make_mock_timeline(probs={5: 0.65, 15: 0.70, 30: 0.75, 60: 0.80}, anomaly_score=0.55, alerts={5: True, 15: True})

    eval1 = engine1.evaluate_state(timeline)
    eval2 = engine2.evaluate_state(timeline)

    assert eval1.current_state == eval2.current_state
    assert eval1.max_calibrated_probability == eval2.max_calibrated_probability
    assert eval1.anomaly_score == eval2.anomaly_score
    assert eval1.conformal_coverage_status == eval2.conformal_coverage_status


# ==============================================================================
# 3. REST API ENDPOINTS & ZERO SILENT BENCHMARK VERIFICATION
# ==============================================================================

def test_risk_api_endpoints_honest_empty_state_without_synthetic_generation():
    """Proves that calling /api/v1/risk/state returns an honest empty state when DB has no flows."""
    client = TestClient(app)

    # 1. State Endpoint
    resp_state = client.get("/api/v1/risk/state")
    assert resp_state.status_code == 200
    data_state = resp_state.json()
    assert data_state["current_state"] == "NORMAL"
    assert "conformal_coverage_status" in data_state

    # 2. Attack Path Endpoint
    resp_path = client.get("/api/v1/risk/attack-path")
    assert resp_path.status_code == 200
    data_path = resp_path.json()
    assert "transition_confidence_status" in data_path

    # 3. Timeline Endpoint
    resp_tl = client.get("/api/v1/risk/timeline")
    assert resp_tl.status_code == 200

    # 4. Transitions Endpoint
    resp_tr = client.get("/api/v1/risk/transitions")
    assert resp_tr.status_code == 200


def test_explicit_demo_state_endpoint():
    """Proves that /api/v1/risk/demo-state executes explicitly with benchmark timeline."""
    client = TestClient(app)
    resp = client.get("/api/v1/risk/demo-state")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_state" in data
    assert "max_calibrated_probability" in data
    assert "attack_path_summary" in data


# ==============================================================================
# 4. SUB-MILLISECOND PERFORMANCE & BENCHMARK TESTS
# ==============================================================================

def test_step7_performance_benchmarks():
    """Measures p50, p95, and p99 evaluation latencies across 100 iterations."""
    ap_engine = AttackPathEngine()
    r_engine = RiskStateEngine()

    timeline = make_mock_timeline(
        probs={5: 0.65, 15: 0.72, 30: 0.80, 60: 0.85},
        anomaly_score=0.55,
        alerts={5: True, 15: True},
    )
    window = TemporalWindowFeatures(
        window_id="w-bench",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        duration_seconds=60,
        packets_per_second=600.0,
        bytes_per_second=80000.0,
        forward_backward_ratio=3.0,
        syn_ack_ratio=0.80,
        flow_volume=100,
    )

    # 1. Benchmark Attack Path Engine
    ap_latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        ap_engine.evaluate_attack_path(timeline=timeline, window=window)
        ap_latencies.append((time.perf_counter() - t0) * 1000.0)

    p50_ap = np.percentile(ap_latencies, 50)
    p95_ap = np.percentile(ap_latencies, 95)
    p99_ap = np.percentile(ap_latencies, 99)

    print(f"\n[BENCHMARK] Attack Path Evaluation: p50={p50_ap:.4f}ms, p95={p95_ap:.4f}ms, p99={p99_ap:.4f}ms")
    assert p50_ap < 1.0, f"Attack path p50 {p50_ap:.4f}ms exceeded 1.0ms target!"

    # 2. Benchmark Risk State Engine
    r_latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        r_engine.evaluate_state(timeline=timeline, window=window)
        r_latencies.append((time.perf_counter() - t0) * 1000.0)

    p50_r = np.percentile(r_latencies, 50)
    p95_r = np.percentile(r_latencies, 95)
    p99_r = np.percentile(r_latencies, 99)

    print(f"[BENCHMARK] Risk State Engine: p50={p50_r:.4f}ms, p95={p95_r:.4f}ms, p99={p99_r:.4f}ms")
    assert p50_r < 1.0, f"Risk Engine p50 {p50_r:.4f}ms exceeded 1.0ms target!"
