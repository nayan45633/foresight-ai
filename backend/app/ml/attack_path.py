"""Foresight AI - Evidence-Constrained Attack Path Forecasting Engine (Step 7.1 Hardened).

Constructs directed attack-stage transition graphs and evaluates whether forward-looking
attack stage transitions are statistically supported by multi-horizon calibrated models,
unsupervised anomaly scores, and TreeSHAP attribution.

Separates Domain Graph Knowledge (valid stage transitions) from Forecasted Probabilities
(statistically validated forward risk). Zero fabricated downstream probabilities.
"""

from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.ml.contracts import (
    AttackPathEdge,
    AttackPathForecast,
    AttackPathNode,
    AttackStageEnum,
    MultiHorizonTimeline,
    TemporalWindowFeatures,
    TransitionConfidenceStatusEnum,
)


class AttackPathEngine:
    """Evidence-constrained engine for attack stage classification and transition forecasting."""

    # Canonical taxonomy sequence for cyber attack stages (MITRE ATT&CK / Kill Chain alignment)
    KILL_CHAIN_STAGES = [
        AttackStageEnum.RECONNAISSANCE.value,
        AttackStageEnum.SCANNING.value,
        AttackStageEnum.INITIAL_ACCESS.value,
        AttackStageEnum.EXECUTION.value,
        AttackStageEnum.PERSISTENCE.value,
        AttackStageEnum.PRIVILEGE_ESCALATION.value,
        AttackStageEnum.LATERAL_MOVEMENT.value,
        AttackStageEnum.COMMAND_AND_CONTROL.value,
        AttackStageEnum.EXFILTRATION.value,
        AttackStageEnum.IMPACT.value,
    ]

    # Valid domain graph transitions between stages (Graph Knowledge Topology)
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        AttackStageEnum.RECONNAISSANCE.value: [
            AttackStageEnum.SCANNING.value,
            AttackStageEnum.INITIAL_ACCESS.value,
        ],
        AttackStageEnum.SCANNING.value: [
            AttackStageEnum.INITIAL_ACCESS.value,
            AttackStageEnum.EXECUTION.value,
        ],
        AttackStageEnum.INITIAL_ACCESS.value: [
            AttackStageEnum.EXECUTION.value,
            AttackStageEnum.PERSISTENCE.value,
            AttackStageEnum.COMMAND_AND_CONTROL.value,
        ],
        AttackStageEnum.EXECUTION.value: [
            AttackStageEnum.PERSISTENCE.value,
            AttackStageEnum.PRIVILEGE_ESCALATION.value,
            AttackStageEnum.COMMAND_AND_CONTROL.value,
            AttackStageEnum.LATERAL_MOVEMENT.value,
        ],
        AttackStageEnum.PERSISTENCE.value: [
            AttackStageEnum.PRIVILEGE_ESCALATION.value,
            AttackStageEnum.COMMAND_AND_CONTROL.value,
            AttackStageEnum.LATERAL_MOVEMENT.value,
        ],
        AttackStageEnum.PRIVILEGE_ESCALATION.value: [
            AttackStageEnum.LATERAL_MOVEMENT.value,
            AttackStageEnum.COMMAND_AND_CONTROL.value,
            AttackStageEnum.EXFILTRATION.value,
            AttackStageEnum.IMPACT.value,
        ],
        AttackStageEnum.LATERAL_MOVEMENT.value: [
            AttackStageEnum.COMMAND_AND_CONTROL.value,
            AttackStageEnum.EXFILTRATION.value,
            AttackStageEnum.IMPACT.value,
        ],
        AttackStageEnum.COMMAND_AND_CONTROL.value: [
            AttackStageEnum.EXFILTRATION.value,
            AttackStageEnum.IMPACT.value,
            AttackStageEnum.LATERAL_MOVEMENT.value,
        ],
        AttackStageEnum.EXFILTRATION.value: [
            AttackStageEnum.IMPACT.value,
        ],
        AttackStageEnum.IMPACT.value: [],
    }

    def evaluate_empty_state(self, target_entity: str = "GLOBAL_PERIMETER", model_version: str = "v1.0.0-temporal-gbm") -> AttackPathForecast:
        """Returns an honest empty state when no validated telemetry is available."""
        now_ts = datetime.now(timezone.utc)
        return AttackPathForecast(
            forecast_id=f"apf-{uuid.uuid4().hex[:12]}",
            forecast_timestamp=now_ts,
            target_entity=target_entity,
            current_stage=None,
            predicted_next_stage=None,
            subsequent_stages=[],
            probability=None,
            uncertainty="LOW",
            evidence=["Awaiting validated telemetry stream."],
            supporting_features=[],
            horizon_minutes=None,
            target_timestamp=None,
            transition_confidence_status=TransitionConfidenceStatusEnum.AWAITING_TELEMETRY.value,
            model_version=model_version,
            graph_nodes=[],
            graph_edges=[],
        )

    def evaluate_attack_path(
        self,
        timeline: MultiHorizonTimeline,
        window: Optional[TemporalWindowFeatures] = None,
        top_shap_features: Optional[List[Dict[str, Any]]] = None,
        model_version: str = "v1.0.0-temporal-gbm",
    ) -> AttackPathForecast:
        """Evaluates observed telemetry and multi-horizon forecasts to predict attack path transitions."""
        forecast_ts = timeline.forecast_timestamp or datetime.now(timezone.utc)
        forecast_id = f"apf-{uuid.uuid4().hex[:12]}"

        # 1. Check if timeline has horizons
        if not timeline.horizons:
            return self.evaluate_empty_state(target_entity=timeline.target_entity, model_version=model_version)

        # 2. Determine if telemetry warrants active attack path evaluation
        is_alert_active = timeline.is_alert_active_any_horizon
        max_prob = 0.0
        
        for h_intel in timeline.horizons:
            if h_intel.calibrated_probability > max_prob:
                max_prob = h_intel.calibrated_probability

        # Check for nominal / benign state
        if not is_alert_active and max_prob < 0.28 and timeline.anomaly_score < 0.35:
            return AttackPathForecast(
                forecast_id=forecast_id,
                forecast_timestamp=forecast_ts,
                target_entity=timeline.target_entity,
                current_stage=AttackStageEnum.BENIGN.value,
                predicted_next_stage=None,
                subsequent_stages=[],
                probability=None,
                uncertainty="LOW",
                evidence=[
                    "Telemetry conforms to baseline nominal distribution.",
                    "No multi-horizon forecast thresholds exceeded.",
                    f"Max forward risk probability: {(max_prob * 100):.1f}%.",
                ],
                supporting_features=[],
                horizon_minutes=None,
                target_timestamp=None,
                transition_confidence_status=TransitionConfidenceStatusEnum.BENIGN_NOMINAL.value,
                model_version=model_version,
                graph_nodes=[
                    AttackPathNode(
                        stage=AttackStageEnum.BENIGN.value,
                        is_current=True,
                        is_predicted=False,
                        is_forecasted=False,
                        probability=round(1.0 - max_prob, 4),
                        evidence_strength="VERIFIED",
                        status="OBSERVED",
                        supporting_features=[],
                        timestamp=forecast_ts,
                    )
                ],
                graph_edges=[],
            )

        # 3. Extract telemetry behavioral indicators to identify current observed stage
        current_stage, stage_evidence, supporting_feats = self._infer_current_stage(
            window=window,
            anomaly_score=timeline.anomaly_score,
            top_shap=top_shap_features,
            max_prob=max_prob,
        )

        # 4. Predict next attack stage based on graph knowledge & multi-horizon trajectory
        next_stage, subsequent_stages, transition_prob, trans_horizon, edge_reasons, uncertainty, is_supported = self._predict_next_stage(
            current_stage=current_stage,
            timeline=timeline,
            top_shap=top_shap_features,
            max_prob=max_prob,
        )

        target_ts = forecast_ts + timedelta(minutes=trans_horizon) if trans_horizon else None

        # 5. Construct graph representation with strict separation of forecasts vs graph topology
        nodes, edges = self._build_path_graph(
            current_stage=current_stage,
            next_stage=next_stage,
            subsequent_stages=subsequent_stages,
            transition_prob=transition_prob,
            trans_horizon=trans_horizon,
            edge_reasons=edge_reasons,
            uncertainty=uncertainty,
            supporting_feats=supporting_feats,
            forecast_ts=forecast_ts,
            target_ts=target_ts,
            is_supported=is_supported,
        )

        status = (
            TransitionConfidenceStatusEnum.VALIDATED_TRANSITION.value
            if is_supported and next_stage is not None and transition_prob and transition_prob >= 0.25
            else TransitionConfidenceStatusEnum.INSUFFICIENT_EVIDENCE.value
        )

        return AttackPathForecast(
            forecast_id=forecast_id,
            forecast_timestamp=forecast_ts,
            target_entity=timeline.target_entity,
            current_stage=current_stage,
            predicted_next_stage=next_stage if is_supported else None,
            subsequent_stages=subsequent_stages,
            probability=transition_prob if is_supported else None,
            uncertainty=uncertainty,
            evidence=stage_evidence + edge_reasons,
            supporting_features=supporting_feats,
            horizon_minutes=trans_horizon if is_supported else None,
            target_timestamp=target_ts if is_supported else None,
            transition_confidence_status=status,
            model_version=model_version,
            graph_nodes=nodes,
            graph_edges=edges,
        )

    def _infer_current_stage(
        self,
        window: Optional[TemporalWindowFeatures],
        anomaly_score: float,
        top_shap: Optional[List[Dict[str, Any]]],
        max_prob: float,
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """Infers the most supported current attack stage from telemetry features and SHAP drivers."""
        evidence: List[str] = []
        supporting_features: List[Dict[str, Any]] = []

        if window is None:
            evidence.append("Window telemetry stream awaiting full temporal reconstruction.")
            return AttackStageEnum.RECONNAISSANCE.value, evidence, supporting_features

        # Telemetry feature calculus
        syn_ratio = (
            getattr(window, "syn_ack_ratio", 0.0)
            or getattr(window, "syn_rate", 0.0)
            or getattr(window, "syn_ratio", 0.0)
            or 0.0
        )
        pps = getattr(window, "packets_per_second", 0.0) or 0.0
        bps = getattr(window, "bytes_per_second", 0.0) or 0.0
        fwd_bwd_ratio = getattr(window, "forward_backward_ratio", 1.0) or 1.0
        rst_ratio = getattr(window, "rst_ratio", 0.0) or 0.0
        flow_vol = getattr(window, "flow_volume", 0) or 0
        bwd_bytes = getattr(window, "backward_bytes_total", 0) or 0

        # Incorporate top SHAP positive contributors
        if top_shap:
            for feat in top_shap[:5]:
                supporting_features.append({
                    "feature_name": feat.get("feature_name", ""),
                    "observed_value": feat.get("observed_value", 0),
                    "shap_value": feat.get("shap_value", 0.0),
                    "unit": feat.get("unit", ""),
                })

        # Evidence-constrained classification rules based on network signatures
        if syn_ratio > 0.5 or (pps > 400 and fwd_bwd_ratio > 3.0 and flow_vol > 50):
            evidence.append(f"Elevated SYN ratio ({syn_ratio:.2f}) and high flow density ({flow_vol} flows) indicate active scanning/probing.")
            return AttackStageEnum.SCANNING.value, evidence, supporting_features

        if pps > 1000 or rst_ratio > 0.45 or (bps > 500000 and anomaly_score > 0.7):
            evidence.append(f"Massive packet/byte rate ({pps:.0f} pps, {bps/1024:.1f} KB/s) and RST ratio ({rst_ratio:.2f}) reflect active volumetric disruption.")
            return AttackStageEnum.IMPACT.value, evidence, supporting_features

        if bwd_bytes > 500000 or (fwd_bwd_ratio < 0.2 and bps > 200000):
            evidence.append(f"High egress data transfer ({bwd_bytes/1024:.1f} KB) with heavy asymmetric download ratio reflects exfiltration.")
            return AttackStageEnum.EXFILTRATION.value, evidence, supporting_features

        if anomaly_score > 0.5 and (fwd_bwd_ratio > 2.0 or syn_ratio > 0.3):
            evidence.append(f"Behavioral anomaly score ({anomaly_score:.2f}) and payload asymmetry indicate initial exploitation attempt.")
            return AttackStageEnum.INITIAL_ACCESS.value, evidence, supporting_features

        if max_prob > 0.40:
            evidence.append(f"High forward risk probability ({(max_prob*100):.1f}%) with persistent telemetry flow.")
            return AttackStageEnum.INITIAL_ACCESS.value, evidence, supporting_features

        evidence.append(f"Low-level telemetry activity detected (anomaly score: {anomaly_score:.2f}).")
        return AttackStageEnum.RECONNAISSANCE.value, evidence, supporting_features

    def _predict_next_stage(
        self,
        current_stage: str,
        timeline: MultiHorizonTimeline,
        top_shap: Optional[List[Dict[str, Any]]],
        max_prob: float,
    ) -> Tuple[Optional[str], List[str], Optional[float], Optional[int], List[str], str, bool]:
        """Predicts the next probable attack stage and subsequent domain graph stages."""
        reasons: List[str] = []
        possible_next = self.VALID_TRANSITIONS.get(current_stage, [])

        if not possible_next:
            reasons.append(f"Stage '{current_stage}' represents terminal or highest-severity phase in graph.")
            return None, [], None, None, reasons, "LOW", False

        # Determine target horizon
        earliest_h = timeline.earliest_warning_horizon_minutes or 15
        h_intel = timeline.horizons[0] if timeline.horizons else None
        for h in timeline.horizons:
            if h.horizon_minutes == earliest_h:
                h_intel = h
                break

        trans_prob = h_intel.calibrated_probability if h_intel else max_prob
        uncertainty = h_intel.uncertainty_level if h_intel else "MEDIUM"

        primary_next = possible_next[0]
        subsequent = possible_next[1:] if len(possible_next) > 1 else []

        # If forward models don't support transition (risk is low / benign)
        is_supported = trans_prob >= 0.25 or (h_intel is not None and h_intel.binary_alert_decision)

        if not is_supported:
            reasons.append("Insufficient evidence for next-stage forecast (forward calibrated probability below alert threshold).")
            return primary_next, subsequent, None, None, reasons, uncertainty, False

        # If high forward risk on far horizons, adjust target stage
        for h in timeline.horizons:
            if h.horizon_minutes >= 30 and h.calibrated_probability > 0.60:
                if AttackStageEnum.EXFILTRATION.value in possible_next:
                    primary_next = AttackStageEnum.EXFILTRATION.value
                elif AttackStageEnum.IMPACT.value in possible_next:
                    primary_next = AttackStageEnum.IMPACT.value

        reasons.append(
            f"Forward model indicates potential escalation from {current_stage} to {primary_next} within +{earliest_h}m (P = {(trans_prob*100):.1f}%)."
        )

        return primary_next, subsequent, round(trans_prob, 4), earliest_h, reasons, uncertainty, True

    def _build_path_graph(
        self,
        current_stage: str,
        next_stage: Optional[str],
        subsequent_stages: List[str],
        transition_prob: Optional[float],
        trans_horizon: Optional[int],
        edge_reasons: List[str],
        uncertainty: str,
        supporting_feats: List[Dict[str, Any]],
        forecast_ts: datetime,
        target_ts: Optional[datetime],
        is_supported: bool,
    ) -> Tuple[List[AttackPathNode], List[AttackPathEdge]]:
        """Constructs the node and edge graph strictly separating forecasts from domain graph topology."""
        nodes: List[AttackPathNode] = []
        edges: List[AttackPathEdge] = []

        # 1. Current Observed Node
        nodes.append(
            AttackPathNode(
                stage=current_stage,
                is_current=True,
                is_predicted=False,
                is_forecasted=False,
                probability=1.0,
                evidence_strength="VERIFIED",
                status="OBSERVED",
                supporting_features=supporting_feats,
                timestamp=forecast_ts,
            )
        )

        if next_stage:
            if is_supported and transition_prob is not None:
                # 2. Predicted Next Node (Statistically supported forecast)
                nodes.append(
                    AttackPathNode(
                        stage=next_stage,
                        is_current=False,
                        is_predicted=True,
                        is_forecasted=True,
                        probability=transition_prob,
                        evidence_strength="HIGH" if transition_prob >= 0.5 else "MEDIUM",
                        status="PREDICTED",
                        supporting_features=supporting_feats,
                        timestamp=target_ts,
                    )
                )

                # Edge from Current to Next (Forecasted Edge)
                edges.append(
                    AttackPathEdge(
                        source_stage=current_stage,
                        target_stage=next_stage,
                        transition_probability=transition_prob,
                        is_forecasted=True,
                        transition_horizon_minutes=trans_horizon,
                        evidence_reasons=edge_reasons,
                        uncertainty=uncertainty,
                        status="VALIDATED",
                    )
                )
            else:
                # Next stage is graph-possible but unvalidated / insufficient evidence
                nodes.append(
                    AttackPathNode(
                        stage=next_stage,
                        is_current=False,
                        is_predicted=False,
                        is_forecasted=False,
                        probability=None,
                        evidence_strength="INSUFFICIENT_EVIDENCE",
                        status="POTENTIAL_UNVALIDATED",
                        supporting_features=[],
                        timestamp=None,
                    )
                )

                edges.append(
                    AttackPathEdge(
                        source_stage=current_stage,
                        target_stage=next_stage,
                        transition_probability=None,
                        is_forecasted=False,
                        transition_horizon_minutes=None,
                        evidence_reasons=["Possible domain graph transition (insufficient telemetry evidence for probability estimation)."],
                        uncertainty="HIGH",
                        status="GRAPH_POSSIBLE",
                    )
                )

            # 3. Downstream Subsequent Stages (Domain Graph Knowledge Only — ZERO fake probabilities)
            for sub_stage in subsequent_stages[:2]:
                nodes.append(
                    AttackPathNode(
                        stage=sub_stage,
                        is_current=False,
                        is_predicted=False,
                        is_forecasted=False,
                        probability=None,  # Zero fabricated probability
                        evidence_strength="INSUFFICIENT_EVIDENCE",
                        status="POTENTIAL_UNVALIDATED",
                        supporting_features=[],
                        timestamp=None,
                    )
                )

                edges.append(
                    AttackPathEdge(
                        source_stage=next_stage,
                        target_stage=sub_stage,
                        transition_probability=None,  # Zero fabricated probability
                        is_forecasted=False,
                        transition_horizon_minutes=None,
                        evidence_reasons=[f"Possible domain graph transition into {sub_stage} (domain taxonomy knowledge, unvalidated)."],
                        uncertainty="HIGH",
                        status="GRAPH_POSSIBLE",
                    )
                )

        return nodes, edges
