"""Foresight AI - Risk State Engine with Hysteresis & Signal Aggregation (Step 7.1 Hardened).

Maintains a deterministic 5-tier security risk state machine (NORMAL -> WATCH -> SUSPICIOUS -> ELEVATED -> CRITICAL)
with configurable hysteresis, minimum persistence durations, cooldown mechanics, and an auditable transition log.

COMPOSITE RISK FORMULATION & TRANSPARENT SIGNAL ROLES:
------------------------------------------------------
The risk evaluation aggregates 5 transparent signal sources:
1. Max Calibrated Probability (w=0.35): Peak forward attack likelihood across +5m, +15m, +30m, +60m horizons.
2. Near-Horizon Imminent Risk (w=0.25): Average calibrated probability of +5m and +15m horizons.
3. Unsupervised Anomaly Score (w=0.20): Isolation Forest score capturing behavioral flow anomalies.
4. Active Alert Horizons Count: Count of horizons where calibrated probability exceeds validation decision thresholds.
5. Conformal Coverage Uncertainty: Penalty weight applied if conformal prediction sets are ambiguous {0, 1}.

Note on Heuristics: State classification boundaries (0.20, 0.40, 0.65, 0.85) and de-escalation dampening rules
are heuristic operational thresholds designed for SOC alert prioritization and anti-flutter stabilization.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.ml.attack_path import AttackPathEngine
from app.ml.contracts import (
    AttackPathForecast,
    MultiHorizonTimeline,
    RiskStateEnum,
    RiskStateEvaluation,
    RiskStateTransition,
    RiskTimelineResponse,
    TemporalWindowFeatures,
)


class RiskStateEngine:
    """Production risk state machine evaluating multi-horizon signals with anti-oscillation hysteresis."""

    def __init__(
        self,
        min_persistence_cycles: int = 2,
        model_version: str = "v1.0.0-temporal-gbm",
    ):
        self.min_persistence_cycles = min_persistence_cycles
        self.model_version = model_version
        
        # State Machine State
        self.current_state: RiskStateEnum = RiskStateEnum.NORMAL
        self.previous_state: RiskStateEnum = RiskStateEnum.NORMAL
        self.state_entry_timestamp: datetime = datetime.now(timezone.utc)
        self.cycles_in_current_state: int = 1
        self.consecutive_calm_cycles: int = 0

        # Audit History
        self.transition_history: List[RiskStateTransition] = []
        self.evaluation_history: List[RiskStateEvaluation] = []
        self.attack_path_engine = AttackPathEngine()

    def evaluate_empty_state(self, model_version: Optional[str] = None) -> RiskStateEvaluation:
        """Returns an honest empty evaluation when no validated telemetry is available."""
        now_ts = datetime.now(timezone.utc)
        eval_id = f"rse-{uuid.uuid4().hex[:12]}"
        version = model_version or self.model_version

        empty_attack_path = self.attack_path_engine.evaluate_empty_state(model_version=version)

        return RiskStateEvaluation(
            evaluation_id=eval_id,
            timestamp=now_ts,
            current_state=RiskStateEnum.NORMAL,
            previous_state=self.previous_state,
            state_duration_seconds=0.0,
            cycles_in_state=self.cycles_in_current_state,
            is_hysteresis_dampened=False,
            hysteresis_notes=["Awaiting validated telemetry stream."],
            max_calibrated_probability=0.0,
            triggering_horizon_minutes=None,
            active_alert_horizons=[],
            anomaly_score=0.0,
            conformal_coverage_status="AWAITING_TELEMETRY",
            uncertainty_level="LOW",
            evidence_summary=["Awaiting validated telemetry stream."],
            top_risk_features=[],
            attack_path_summary=empty_attack_path,
            model_version=version,
        )

    def evaluate_state(
        self,
        timeline: MultiHorizonTimeline,
        window: Optional[TemporalWindowFeatures] = None,
        top_shap_features: Optional[List[Dict[str, Any]]] = None,
    ) -> RiskStateEvaluation:
        """Evaluates multi-horizon signals and applies deterministic state transitions with hysteresis."""
        now_ts = timeline.forecast_timestamp or datetime.now(timezone.utc)
        eval_id = f"rse-{uuid.uuid4().hex[:12]}"

        if not timeline.horizons:
            return self.evaluate_empty_state()

        # 1. Compute multi-horizon aggregate metrics
        max_prob = 0.0
        max_h: Optional[int] = None
        active_alert_horizons: List[int] = []
        conformal_coverage = "NORMAL"
        uncertainty_level = "LOW"
        
        for h_intel in timeline.horizons:
            if h_intel.calibrated_probability > max_prob:
                max_prob = h_intel.calibrated_probability
                max_h = h_intel.horizon_minutes

            if h_intel.binary_alert_decision:
                active_alert_horizons.append(h_intel.horizon_minutes)

            pred_set = h_intel.conformal_prediction_set.prediction_set if hasattr(h_intel.conformal_prediction_set, "prediction_set") else (h_intel.conformal_prediction_set if isinstance(h_intel.conformal_prediction_set, list) else [])
            if len(pred_set) == 2:
                conformal_coverage = "AMBIGUOUS"
                uncertainty_level = "HIGH"
            elif pred_set == [1]:
                conformal_coverage = "ATTACK_COVERED"

        anomaly_score = timeline.anomaly_score

        # 2. Evaluate Attack Path
        attack_path = self.attack_path_engine.evaluate_attack_path(
            timeline=timeline,
            window=window,
            top_shap_features=top_shap_features,
            model_version=self.model_version,
        )

        # 3. Determine Raw Target State based on aggregated signals
        raw_target_state, evidence_notes = self._calculate_raw_target_state(
            max_prob=max_prob,
            max_h=max_h,
            active_alert_horizons=active_alert_horizons,
            anomaly_score=anomaly_score,
            conformal_coverage=conformal_coverage,
            attack_path=attack_path,
        )

        # 4. Apply Hysteresis and Persistence Rules
        final_state, is_dampened, hysteresis_notes = self._apply_hysteresis(
            raw_target_state=raw_target_state,
            max_prob=max_prob,
            anomaly_score=anomaly_score,
            active_alerts_count=len(active_alert_horizons),
        )

        # 5. Handle State Transition & Audit Trail
        is_transition = final_state != self.current_state
        state_duration = (now_ts - self.state_entry_timestamp).total_seconds()

        if is_transition:
            transition = RiskStateTransition(
                transition_id=f"rst-{uuid.uuid4().hex[:12]}",
                timestamp=now_ts,
                previous_state=self.current_state,
                new_state=final_state,
                triggering_evidence=evidence_notes,
                forecast_probability=round(max_prob, 4),
                anomaly_score=round(anomaly_score, 4),
                uncertainty=uncertainty_level,
                triggering_horizon=max_h,
                reason=f"State changed from {self.current_state.value} to {final_state.value} ({evidence_notes[0] if evidence_notes else 'Signal update'})",
                model_version=self.model_version,
            )
            self.transition_history.append(transition)
            self.previous_state = self.current_state
            self.current_state = final_state
            self.state_entry_timestamp = now_ts
            self.cycles_in_current_state = 1
            state_duration = 0.0
        else:
            self.cycles_in_current_state += 1

        top_feats: List[Dict[str, Any]] = []
        if top_shap_features:
            top_feats = top_shap_features[:5]

        evaluation = RiskStateEvaluation(
            evaluation_id=eval_id,
            timestamp=now_ts,
            current_state=self.current_state,
            previous_state=self.previous_state,
            state_duration_seconds=round(state_duration, 1),
            cycles_in_state=self.cycles_in_current_state,
            is_hysteresis_dampened=is_dampened,
            hysteresis_notes=hysteresis_notes,
            max_calibrated_probability=round(max_prob, 4),
            triggering_horizon_minutes=max_h,
            active_alert_horizons=active_alert_horizons,
            anomaly_score=round(anomaly_score, 4),
            conformal_coverage_status=conformal_coverage,
            uncertainty_level=uncertainty_level,
            evidence_summary=evidence_notes,
            top_risk_features=top_feats,
            attack_path_summary=attack_path,
            model_version=self.model_version,
        )

        self.evaluation_history.append(evaluation)
        # Cap evaluation history in memory
        if len(self.evaluation_history) > 200:
            self.evaluation_history = self.evaluation_history[-200:]
        if len(self.transition_history) > 100:
            self.transition_history = self.transition_history[-100:]

        return evaluation

    def _calculate_raw_target_state(
        self,
        max_prob: float,
        max_h: Optional[int],
        active_alert_horizons: List[int],
        anomaly_score: float,
        conformal_coverage: str,
        attack_path: AttackPathForecast,
    ) -> Tuple[RiskStateEnum, List[str]]:
        """Interpretable scoring logic mapping multi-horizon signals to candidate risk state."""
        evidence: List[str] = []
        alert_count = len(active_alert_horizons)

        # 1. CRITICAL
        if (max_prob >= 0.70 and anomaly_score >= 0.50) or alert_count >= 3 or (5 in active_alert_horizons and max_prob >= 0.75):
            evidence.append(
                f"Critical risk escalation: Max risk probability {(max_prob*100):.1f}% with {alert_count} active alert horizons and anomaly score {anomaly_score:.2f}."
            )
            return RiskStateEnum.CRITICAL, evidence

        # 2. ELEVATED
        if alert_count >= 2 or (max_prob >= 0.60 and alert_count >= 1) or (5 in active_alert_horizons and max_prob >= 0.50):
            evidence.append(
                f"Elevated risk: {alert_count} multi-horizon alerts active (triggering horizons: {active_alert_horizons}, max prob: {(max_prob*100):.1f}%)."
            )
            return RiskStateEnum.ELEVATED, evidence

        # 3. SUSPICIOUS
        if alert_count >= 1 or (anomaly_score >= 0.50 and conformal_coverage == "AMBIGUOUS") or max_prob >= 0.35:
            evidence.append(
                f"Suspicious telemetry behavior: Single horizon alert or elevated probability ({(max_prob*100):.1f}%, anomaly: {anomaly_score:.2f})."
            )
            return RiskStateEnum.SUSPICIOUS, evidence

        # 4. WATCH
        if (0.28 <= anomaly_score < 0.50) or max_prob >= 0.22 or (60 in active_alert_horizons):
            evidence.append(
                f"Watch state: Mild anomaly signature ({anomaly_score:.2f}) or early risk drift on forward horizon (max prob: {(max_prob*100):.1f}%)."
            )
            return RiskStateEnum.WATCH, evidence

        # 5. NORMAL
        evidence.append("All multi-horizon forecasting models and telemetry detectors indicate baseline nominal conditions.")
        return RiskStateEnum.NORMAL, evidence

    def _apply_hysteresis(
        self,
        raw_target_state: RiskStateEnum,
        max_prob: float,
        anomaly_score: float,
        active_alerts_count: int,
    ) -> Tuple[RiskStateEnum, bool, List[str]]:
        """Applies hysteresis, persistence buffers, and de-escalation dampening."""
        state_ranks = {
            RiskStateEnum.NORMAL: 0,
            RiskStateEnum.WATCH: 1,
            RiskStateEnum.SUSPICIOUS: 2,
            RiskStateEnum.ELEVATED: 3,
            RiskStateEnum.CRITICAL: 4,
        }

        current_rank = state_ranks[self.current_state]
        target_rank = state_ranks[raw_target_state]
        notes: List[str] = []

        # Escalation: Responsive and immediate
        if target_rank > current_rank:
            self.consecutive_calm_cycles = 0
            notes.append(f"Immediate escalation from {self.current_state.value} to {raw_target_state.value} on verified risk signal.")
            return raw_target_state, False, notes

        # Same State: Maintain
        if target_rank == current_rank:
            self.consecutive_calm_cycles = 0
            return self.current_state, False, notes

        # De-escalation: Requires persistence duration and conservative de-escalation thresholds
        if target_rank < current_rank:
            self.consecutive_calm_cycles += 1
            # Check minimum consecutive persistence cycle requirement
            if self.consecutive_calm_cycles < self.min_persistence_cycles:
                notes.append(
                    f"Hysteresis active: Retaining {self.current_state.value} (calm cycle {self.consecutive_calm_cycles}/{self.min_persistence_cycles} before de-escalation)."
                )
                return self.current_state, True, notes

            # Strict de-escalation threshold checks to avoid flutter
            if self.current_state == RiskStateEnum.CRITICAL:
                if max_prob > 0.45 or active_alerts_count >= 2:
                    notes.append("Hysteresis active: Risk probability remains elevated, dampening de-escalation from CRITICAL.")
                    return RiskStateEnum.CRITICAL, True, notes
                # Step-down by at most 1 level per transition to ensure smooth de-escalation
                step_down = RiskStateEnum.ELEVATED
                self.consecutive_calm_cycles = 0
                notes.append(f"Controlled de-escalation from CRITICAL to {step_down.value}.")
                return step_down, False, notes

            elif self.current_state == RiskStateEnum.ELEVATED:
                if max_prob > 0.32 or active_alerts_count >= 1:
                    notes.append("Hysteresis active: Alert active on horizon, dampening de-escalation from ELEVATED.")
                    return RiskStateEnum.ELEVATED, True, notes
                step_down = RiskStateEnum.SUSPICIOUS
                self.consecutive_calm_cycles = 0
                notes.append(f"Controlled de-escalation from ELEVATED to {step_down.value}.")
                return step_down, False, notes

            elif self.current_state == RiskStateEnum.SUSPICIOUS:
                if max_prob > 0.22 or anomaly_score >= 0.40:
                    notes.append("Hysteresis active: Anomaly score or probability not fully calmed.")
                    return RiskStateEnum.SUSPICIOUS, True, notes
                step_down = RiskStateEnum.WATCH
                self.consecutive_calm_cycles = 0
                notes.append(f"Controlled de-escalation from SUSPICIOUS to {step_down.value}.")
                return step_down, False, notes

            elif self.current_state == RiskStateEnum.WATCH:
                if max_prob > 0.15 or anomaly_score >= 0.28:
                    notes.append("Hysteresis active: Telemetry not yet fully back to baseline distribution.")
                    return RiskStateEnum.WATCH, True, notes
                step_down = RiskStateEnum.NORMAL
                self.consecutive_calm_cycles = 0
                notes.append(f"De-escalated to {step_down.value} after verified calm period.")
                return step_down, False, notes

        return self.current_state, False, notes

    def get_timeline_response(self) -> RiskTimelineResponse:
        """Returns the full timeline of risk evaluations and historical transitions."""
        current_eval = self.evaluation_history[-1] if self.evaluation_history else self.evaluate_empty_state()

        return RiskTimelineResponse(
            current_evaluation=current_eval,
            timeline_transitions=list(reversed(self.transition_history)),
            historical_evaluations=list(reversed(self.evaluation_history[-30:])),
        )
