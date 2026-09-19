"""Foresight AI - Counterfactual What-If Forecasting & Model Sensitivity Engine (Step 8).

Performs real model re-inference on perturbed feature inputs to quantify model prediction sensitivity,
decision boundary shifts, conformal prediction set transitions, and TreeSHAP attribution deltas.

SCIENTIFIC PRINCIPLE:
Measures model sensitivity (ΔP_h = P_cf,h - P_base,h) under frozen model parameters.
Does NOT make physical causal claims.
"""

from collections import deque
from datetime import datetime, timezone
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.ml.contracts import (
    AppliedFeaturePerturbation,
    CounterfactualPreset,
    CounterfactualScenarioRequest,
    CounterfactualScenarioResponse,
    DecisionFlipEnum,
    FeatureClassificationEnum,
    FeatureMetadataCatalogResponse,
    FeatureMetadataItem,
    HorizonCounterfactualResult,
    HorizonShapExplanation,
    PerturbationModeEnum,
    ShapDeltaItem,
)
from app.ml.feature_schema import (
    FEATURE_DEFINITIONS,
    FEATURE_NAME_TO_INDEX,
    FEATURE_INDEX_TO_DEF,
    FEATURE_NAMES,
    FeatureDefinition,
    validate_feature_vector,
)


class FeatureRangeConstraint:
    """Specification of allowable numerical bounds and behavior for an input feature."""

    def __init__(
        self,
        index: int,
        name: str,
        min_value: float,
        max_value: float,
        default_value: float,
        slider_step: float,
        classification: FeatureClassificationEnum,
        unit: Optional[str] = None,
    ):
        self.index = index
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value
        self.slider_step = slider_step
        self.classification = classification
        self.unit = unit


# 37 Authoritative Feature Range Constraints & Classifications
FEATURE_CONSTRAINTS: Dict[str, FeatureRangeConstraint] = {
    # 1. Base Window Telemetry (0..27)
    "flow_volume": FeatureRangeConstraint(0, "flow_volume", 0.0, 50000.0, 120.0, 10.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "flows/window"),
    "packet_volume": FeatureRangeConstraint(1, "packet_volume", 0.0, 1000000.0, 4500.0, 50.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets/window"),
    "byte_volume": FeatureRangeConstraint(2, "byte_volume", 0.0, 500000000.0, 2500000.0, 10000.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bytes/window"),
    "packets_per_second": FeatureRangeConstraint(3, "packets_per_second", 0.0, 50000.0, 75.0, 5.0, FeatureClassificationEnum.DERIVED, "packets/s"),
    "bytes_per_second": FeatureRangeConstraint(4, "bytes_per_second", 0.0, 50000000.0, 41666.0, 500.0, FeatureClassificationEnum.DERIVED, "bytes/s"),
    "mean_flow_duration_ms": FeatureRangeConstraint(5, "mean_flow_duration_ms", 0.0, 600000.0, 2400.0, 50.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "ms"),
    "duration_variance": FeatureRangeConstraint(6, "duration_variance", 0.0, 100000000.0, 12000.0, 100.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "ms²"),
    "forward_packets_total": FeatureRangeConstraint(7, "forward_packets_total", 0.0, 1000000.0, 2400.0, 50.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets"),
    "backward_packets_total": FeatureRangeConstraint(8, "backward_packets_total", 0.0, 1000000.0, 2100.0, 50.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets"),
    "forward_bytes_total": FeatureRangeConstraint(9, "forward_bytes_total", 0.0, 500000000.0, 1400000.0, 10000.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bytes"),
    "backward_bytes_total": FeatureRangeConstraint(10, "backward_bytes_total", 0.0, 500000000.0, 1100000.0, 10000.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bytes"),
    "forward_backward_ratio": FeatureRangeConstraint(11, "forward_backward_ratio", 0.0, 100.0, 1.14, 0.05, FeatureClassificationEnum.DERIVED, "ratio"),
    "mean_packet_length": FeatureRangeConstraint(12, "mean_packet_length", 0.0, 9000.0, 555.0, 5.0, FeatureClassificationEnum.DERIVED, "bytes/packet"),
    "packet_length_std": FeatureRangeConstraint(13, "packet_length_std", 0.0, 4500.0, 120.0, 5.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bytes"),
    "syn_count": FeatureRangeConstraint(14, "syn_count", 0.0, 500000.0, 45.0, 5.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets"),
    "syn_rate": FeatureRangeConstraint(15, "syn_rate", 0.0, 10000.0, 0.75, 0.1, FeatureClassificationEnum.DERIVED, "packets/s"),
    "ack_count": FeatureRangeConstraint(16, "ack_count", 0.0, 500000.0, 4200.0, 50.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets"),
    "rst_count": FeatureRangeConstraint(17, "rst_count", 0.0, 100000.0, 12.0, 1.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "packets"),
    "syn_ack_ratio": FeatureRangeConstraint(18, "syn_ack_ratio", 0.0, 500.0, 0.01, 0.01, FeatureClassificationEnum.DERIVED, "ratio"),
    "rst_ratio": FeatureRangeConstraint(19, "rst_ratio", 0.0, 1.0, 0.10, 0.01, FeatureClassificationEnum.DERIVED, "ratio"),
    "unique_source_ips": FeatureRangeConstraint(20, "unique_source_ips", 1.0, 50000.0, 45.0, 1.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "count"),
    "unique_destination_ips": FeatureRangeConstraint(21, "unique_destination_ips", 1.0, 10000.0, 12.0, 1.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "count"),
    "unique_source_ports": FeatureRangeConstraint(22, "unique_source_ports", 1.0, 65535.0, 95.0, 1.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "count"),
    "unique_destination_ports": FeatureRangeConstraint(23, "unique_destination_ports", 1.0, 65535.0, 6.0, 1.0, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "count"),
    "entropy_source_ips": FeatureRangeConstraint(24, "entropy_source_ips", 0.0, 16.0, 2.8, 0.1, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bits"),
    "entropy_dest_ips": FeatureRangeConstraint(25, "entropy_dest_ips", 0.0, 16.0, 1.4, 0.1, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bits"),
    "entropy_source_ports": FeatureRangeConstraint(26, "entropy_source_ports", 0.0, 16.0, 3.9, 0.1, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bits"),
    "entropy_dest_ports": FeatureRangeConstraint(27, "entropy_dest_ports", 0.0, 16.0, 0.8, 0.1, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "bits"),

    # 2. Rolling Temporal Derivatives (28..35)
    "delta_packet_rate": FeatureRangeConstraint(28, "delta_packet_rate", -50000.0, 50000.0, 0.0, 5.0, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "packets/s"),
    "packet_rate_slope": FeatureRangeConstraint(29, "packet_rate_slope", -5000.0, 5000.0, 0.0, 0.5, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "packets/s²"),
    "delta_byte_rate": FeatureRangeConstraint(30, "delta_byte_rate", -50000000.0, 50000000.0, 0.0, 500.0, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "bytes/s"),
    "entropy_change_dest_ports": FeatureRangeConstraint(31, "entropy_change_dest_ports", -16.0, 16.0, 0.0, 0.1, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "bits"),
    "entropy_change_src_ips": FeatureRangeConstraint(32, "entropy_change_src_ips", -16.0, 16.0, 0.0, 0.1, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "bits"),
    "syn_rate_acceleration": FeatureRangeConstraint(33, "syn_rate_acceleration", -5000.0, 5000.0, 0.0, 0.5, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "packets/s²"),
    "burst_score_delta": FeatureRangeConstraint(34, "burst_score_delta", -10.0, 10.0, 0.0, 0.05, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "ratio"),
    "dest_concentration_delta": FeatureRangeConstraint(35, "dest_concentration_delta", -1.0, 1.0, 0.0, 0.01, FeatureClassificationEnum.DEPENDENCY_CONSTRAINED, "ratio"),

    # 3. Behavioral Anomaly Score (36)
    "behavioral_anomaly_score": FeatureRangeConstraint(36, "behavioral_anomaly_score", 0.0, 1.0, 0.05, 0.01, FeatureClassificationEnum.DIRECTLY_PERTURBABLE, "score [0.0, 1.0]"),
}


# Predefined Counterfactual Intervention & Stress-Testing Presets
BUILTIN_PRESETS: List[CounterfactualPreset] = [
    CounterfactualPreset(
        preset_id="syn_flood_mitigation",
        title="SYN Flood Handshake Neutralization",
        category="Mitigation Simulation",
        description="Simulates perimeter SYN proxy mitigation by enforcing balanced SYN/ACK ratios and suppressing incomplete SYN storms.",
        perturbations={
            "syn_count": 50.0,
            "syn_rate": 0.83,
            "syn_ack_ratio": 0.02,
            "rst_count": 8.0,
            "rst_ratio": 0.05,
            "behavioral_anomaly_score": 0.08,
        },
        recompute_derived=False,
        suggested_use_case="Evaluate if dropping SYN flood intensity clears the high-risk multi-horizon alert status.",
    ),
    CounterfactualPreset(
        preset_id="rate_limiting_70",
        title="Perimeter Rate Limiting (70% Volumetric Drop)",
        category="Mitigation Simulation",
        description="Simulates automated upstream bandwidth throttling, curtailing active flow and packet volumes by 70%.",
        perturbations={
            "flow_volume": 150.0,
            "packet_volume": 1200.0,
            "byte_volume": 600000.0,
            "packets_per_second": 20.0,
            "bytes_per_second": 10000.0,
            "delta_packet_rate": -150.0,
            "packet_rate_slope": -10.0,
        },
        recompute_derived=False,
        suggested_use_case="Measure forecast sensitivity to volumetric rate-limiting policies during sustained saturation.",
    ),
    CounterfactualPreset(
        preset_id="port_scan_suppression",
        title="Port Scan Reconnaissance Blockade",
        category="Mitigation Simulation",
        description="Simulates immediate IP-reputation blocking of vertical/horizontal port scanners, collapsing destination port entropy.",
        perturbations={
            "unique_destination_ports": 2.0,
            "entropy_dest_ports": 0.4,
            "entropy_change_dest_ports": -2.5,
            "unique_source_ips": 15.0,
            "behavioral_anomaly_score": 0.12,
        },
        recompute_derived=True,
        suggested_use_case="Verify model sensitivity when hostile port sweep cardinality is suppressed.",
    ),
    CounterfactualPreset(
        preset_id="reconnaissance_escalation",
        title="Adversarial Port Sweep Escalation",
        category="Stress Testing",
        description="Stress tests early warning sensitivity by injecting an aggressive multi-port horizontal reconnaissance pattern.",
        perturbations={
            "unique_destination_ports": 1200.0,
            "entropy_dest_ports": 7.8,
            "entropy_change_dest_ports": 4.5,
            "flow_volume": 2500.0,
            "behavioral_anomaly_score": 0.78,
        },
        recompute_derived=True,
        suggested_use_case="Assess how rapidly early horizons (+5m, +15m) elevate to alert status under reconnaissance surges.",
    ),
    CounterfactualPreset(
        preset_id="ddos_amplification_surge",
        title="Volumetric DDoS Amplification Surge",
        category="Stress Testing",
        description="Simulates massive volumetric surge with high packet rates, asymmetric forward traffic, and severe anomaly scores.",
        perturbations={
            "packet_volume": 250000.0,
            "byte_volume": 180000000.0,
            "packets_per_second": 4166.0,
            "bytes_per_second": 3000000.0,
            "syn_count": 85000.0,
            "syn_ack_ratio": 45.0,
            "forward_backward_ratio": 12.5,
            "behavioral_anomaly_score": 0.95,
        },
        recompute_derived=False,
        suggested_use_case="Verify critical alert triggers and conformal certainty under extreme volumetric stress.",
    ),
]


class CounterfactualEngine:
    """Production Counterfactual What-If Simulation Engine."""

    def __init__(self, history_capacity: int = 100):
        self._history_capacity = history_capacity
        self._scenario_history: deque = deque(maxlen=history_capacity)
        self._scenario_lookup: Dict[str, CounterfactualScenarioResponse] = {}
        self._cached_default_baseline: Optional[np.ndarray] = None

    def get_default_baseline_vector(self, inference_service: Optional[Any] = None) -> np.ndarray:
        """Returns authoritative nominal 37-D baseline feature vector constructed from schema defaults.
        
        Strictly isolated from synthetic benchmark generators.
        """
        if self._cached_default_baseline is not None:
            return self._cached_default_baseline.copy()

        vec = np.zeros((1, 37), dtype=np.float32)
        for feat in FEATURE_DEFINITIONS:
            constraint = FEATURE_CONSTRAINTS.get(feat.name)
            def_val = constraint.default_value if constraint else 0.0
            vec[0, feat.index] = float(def_val)

        self._cached_default_baseline = vec
        return self._cached_default_baseline.copy()



    def get_feature_catalog(self) -> FeatureMetadataCatalogResponse:
        """Returns complete feature catalog with min/max constraints and preset scenarios."""
        items: List[FeatureMetadataItem] = []
        for feat in FEATURE_DEFINITIONS:
            constraint = FEATURE_CONSTRAINTS.get(feat.name)
            if not constraint:
                min_v, max_v, def_v, step = 0.0, 100000.0, 0.0, 1.0
                classification = FeatureClassificationEnum.DIRECTLY_PERTURBABLE.value
            else:
                min_v = constraint.min_value
                max_v = constraint.max_value
                def_v = constraint.default_value
                step = constraint.slider_step
                classification = constraint.classification.value

            items.append(
                FeatureMetadataItem(
                    index=feat.index,
                    name=feat.name,
                    display_name=feat.display_name,
                    datatype=feat.datatype,
                    unit=feat.unit,
                    category=feat.category,
                    classification=classification,
                    min_value=min_v,
                    max_value=max_v,
                    default_value=def_v,
                    slider_step=step,
                    description=feat.description,
                    positive_risk_meaning=feat.positive_risk_meaning,
                    negative_risk_meaning=feat.negative_risk_meaning,
                )
            )

        return FeatureMetadataCatalogResponse(
            schema_version="v1.0.0",
            total_features=len(items),
            features=items,
            presets=BUILTIN_PRESETS,
            scientific_disclaimer=(
                "Measures model prediction sensitivity to perturbed feature inputs under frozen model weights. "
                "This is not a physical causal counterfactual or causal intervention analysis."
            ),
        )

    def validate_perturbations(
        self,
        perturbations: Dict[str, float],
        perturbation_modes: Optional[Dict[str, PerturbationModeEnum]] = None,
    ) -> None:
        """Validates feature perturbation inputs against schema definitions, types, and bounds."""
        if not perturbations:
            raise ValueError("Perturbations dictionary cannot be empty for counterfactual evaluation")

        for feat_name, raw_val in perturbations.items():
            if feat_name not in FEATURE_NAME_TO_INDEX:
                raise ValueError(
                    f"Unknown feature '{feat_name}'. Must match one of the 37 authoritative schema features."
                )

            if raw_val is None or not isinstance(raw_val, (int, float)):
                raise ValueError(f"Feature '{feat_name}' value must be numeric float/int, got {type(raw_val)}")

            if not math.isfinite(raw_val):
                raise ValueError(f"Feature '{feat_name}' value must be finite (got NaN or Inf)")

            mode = perturbation_modes.get(feat_name, PerturbationModeEnum.ABSOLUTE) if perturbation_modes else PerturbationModeEnum.ABSOLUTE
            constraint = FEATURE_CONSTRAINTS.get(feat_name)

            # For ABSOLUTE mode, enforce boundary constraints
            if mode == PerturbationModeEnum.ABSOLUTE and constraint:
                if raw_val < constraint.min_value:
                    raise ValueError(
                        f"Feature '{feat_name}' value {raw_val} is below allowable minimum {constraint.min_value} {constraint.unit or ''}"
                    )
                if raw_val > constraint.max_value:
                    raise ValueError(
                        f"Feature '{feat_name}' value {raw_val} exceeds allowable maximum {constraint.max_value} {constraint.unit or ''}"
                    )

    def compute_counterfactual_vector(
        self,
        baseline_vector: np.ndarray,
        perturbations: Dict[str, float],
        perturbation_modes: Optional[Dict[str, PerturbationModeEnum]] = None,
        recompute_derived: bool = True,
    ) -> Tuple[np.ndarray, List[AppliedFeaturePerturbation]]:
        """Applies validated perturbations and dependency propagation to build the counterfactual vector."""
        if baseline_vector.ndim == 2:
            base = baseline_vector[0].copy()
        else:
            base = baseline_vector.copy()

        cf_vec = base.copy()
        applied_list: List[AppliedFeaturePerturbation] = []

        # 1. Apply explicit user perturbations
        for feat_name, target_val in perturbations.items():
            idx = FEATURE_NAME_TO_INDEX[feat_name]
            orig_val = float(base[idx])
            mode = perturbation_modes.get(feat_name, PerturbationModeEnum.ABSOLUTE) if perturbation_modes else PerturbationModeEnum.ABSOLUTE

            if mode == PerturbationModeEnum.ABSOLUTE:
                new_val = float(target_val)
            elif mode == PerturbationModeEnum.RELATIVE_PERCENT:
                new_val = orig_val * (1.0 + (target_val / 100.0))
            elif mode == PerturbationModeEnum.DELTA:
                new_val = orig_val + target_val
            else:
                new_val = float(target_val)

            constraint = FEATURE_CONSTRAINTS.get(feat_name)
            if constraint:
                new_val = float(np.clip(new_val, constraint.min_value, constraint.max_value))

            cf_vec[idx] = new_val
            delta = new_val - orig_val
            pct = (delta / orig_val * 100.0) if abs(orig_val) > 1e-6 else None
            classification = constraint.classification.value if constraint else "DIRECTLY_PERTURBABLE"

            applied_list.append(
                AppliedFeaturePerturbation(
                    feature_name=feat_name,
                    feature_index=idx,
                    original_value=round(orig_val, 4),
                    perturbed_value=round(new_val, 4),
                    mode=mode.value if hasattr(mode, "value") else str(mode),
                    delta=round(delta, 4),
                    delta_percent=round(pct, 2) if pct is not None else None,
                    classification=classification,
                    unit=constraint.unit if constraint else None,
                    is_derived_auto_sync=False,
                )
            )

        # 2. Recompute derived features if requested and constituent features changed
        if recompute_derived:
            derived_syncs = self._sync_derived_features(base, cf_vec, perturbations)
            applied_list.extend(derived_syncs)

        return cf_vec.reshape(1, -1), applied_list

    def _sync_derived_features(
        self,
        base_vec: np.ndarray,
        cf_vec: np.ndarray,
        explicit_perturbations: Dict[str, float],
    ) -> List[AppliedFeaturePerturbation]:
        """Automatically updates derived mathematical ratios if constituent features were perturbed."""
        syncs: List[AppliedFeaturePerturbation] = []

        # syn_ack_ratio (idx 18) from syn_count (14) & ack_count (16)
        if "syn_ack_ratio" not in explicit_perturbations:
            if "syn_count" in explicit_perturbations or "ack_count" in explicit_perturbations:
                idx = FEATURE_NAME_TO_INDEX["syn_ack_ratio"]
                orig_val = float(base_vec[idx])
                syn_c = float(cf_vec[FEATURE_NAME_TO_INDEX["syn_count"]])
                ack_c = float(cf_vec[FEATURE_NAME_TO_INDEX["ack_count"]])
                new_val = float(np.clip(syn_c / (ack_c + 1e-5), 0.0, 500.0))
                cf_vec[idx] = new_val
                delta = new_val - orig_val
                syncs.append(
                    AppliedFeaturePerturbation(
                        feature_name="syn_ack_ratio",
                        feature_index=idx,
                        original_value=round(orig_val, 4),
                        perturbed_value=round(new_val, 4),
                        mode="AUTO_DERIVED",
                        delta=round(delta, 4),
                        delta_percent=round(delta / orig_val * 100.0, 2) if abs(orig_val) > 1e-6 else None,
                        classification=FeatureClassificationEnum.DERIVED.value,
                        unit="ratio",
                        is_derived_auto_sync=True,
                    )
                )

        # rst_ratio (idx 19) from rst_count (17) & flow_volume (0)
        if "rst_ratio" not in explicit_perturbations:
            if "rst_count" in explicit_perturbations or "flow_volume" in explicit_perturbations:
                idx = FEATURE_NAME_TO_INDEX["rst_ratio"]
                orig_val = float(base_vec[idx])
                rst_c = float(cf_vec[FEATURE_NAME_TO_INDEX["rst_count"]])
                flows = float(cf_vec[FEATURE_NAME_TO_INDEX["flow_volume"]])
                new_val = float(np.clip(rst_c / (flows + 1e-5), 0.0, 1.0))
                cf_vec[idx] = new_val
                delta = new_val - orig_val
                syncs.append(
                    AppliedFeaturePerturbation(
                        feature_name="rst_ratio",
                        feature_index=idx,
                        original_value=round(orig_val, 4),
                        perturbed_value=round(new_val, 4),
                        mode="AUTO_DERIVED",
                        delta=round(delta, 4),
                        delta_percent=round(delta / orig_val * 100.0, 2) if abs(orig_val) > 1e-6 else None,
                        classification=FeatureClassificationEnum.DERIVED.value,
                        unit="ratio",
                        is_derived_auto_sync=True,
                    )
                )

        # packets_per_second (idx 3) from packet_volume (1) assuming 60s window
        if "packets_per_second" not in explicit_perturbations and "packet_volume" in explicit_perturbations:
            idx = FEATURE_NAME_TO_INDEX["packets_per_second"]
            orig_val = float(base_vec[idx])
            pkt_v = float(cf_vec[FEATURE_NAME_TO_INDEX["packet_volume"]])
            new_val = float(np.clip(pkt_v / 60.0, 0.0, 50000.0))
            cf_vec[idx] = new_val
            delta = new_val - orig_val
            syncs.append(
                AppliedFeaturePerturbation(
                    feature_name="packets_per_second",
                    feature_index=idx,
                    original_value=round(orig_val, 4),
                    perturbed_value=round(new_val, 4),
                    mode="AUTO_DERIVED",
                    delta=round(delta, 4),
                    delta_percent=round(delta / orig_val * 100.0, 2) if abs(orig_val) > 1e-6 else None,
                    classification=FeatureClassificationEnum.DERIVED.value,
                    unit="packets/s",
                    is_derived_auto_sync=True,
                )
            )

        # bytes_per_second (idx 4) from byte_volume (2)
        if "bytes_per_second" not in explicit_perturbations and "byte_volume" in explicit_perturbations:
            idx = FEATURE_NAME_TO_INDEX["bytes_per_second"]
            orig_val = float(base_vec[idx])
            byte_v = float(cf_vec[FEATURE_NAME_TO_INDEX["byte_volume"]])
            new_val = float(np.clip(byte_v / 60.0, 0.0, 50000000.0))
            cf_vec[idx] = new_val
            delta = new_val - orig_val
            syncs.append(
                AppliedFeaturePerturbation(
                    feature_name="bytes_per_second",
                    feature_index=idx,
                    original_value=round(orig_val, 4),
                    perturbed_value=round(new_val, 4),
                    mode="AUTO_DERIVED",
                    delta=round(delta, 4),
                    delta_percent=round(delta / orig_val * 100.0, 2) if abs(orig_val) > 1e-6 else None,
                    classification=FeatureClassificationEnum.DERIVED.value,
                    unit="bytes/s",
                    is_derived_auto_sync=True,
                )
            )

        # syn_rate (idx 15) from syn_count (14)
        if "syn_rate" not in explicit_perturbations and "syn_count" in explicit_perturbations:
            idx = FEATURE_NAME_TO_INDEX["syn_rate"]
            orig_val = float(base_vec[idx])
            syn_c = float(cf_vec[FEATURE_NAME_TO_INDEX["syn_count"]])
            new_val = float(np.clip(syn_c / 60.0, 0.0, 10000.0))
            cf_vec[idx] = new_val
            delta = new_val - orig_val
            syncs.append(
                AppliedFeaturePerturbation(
                    feature_name="syn_rate",
                    feature_index=idx,
                    original_value=round(orig_val, 4),
                    perturbed_value=round(new_val, 4),
                    mode="AUTO_DERIVED",
                    delta=round(delta, 4),
                    delta_percent=round(delta / orig_val * 100.0, 2) if abs(orig_val) > 1e-6 else None,
                    classification=FeatureClassificationEnum.DERIVED.value,
                    unit="packets/s",
                    is_derived_auto_sync=True,
                )
            )

        return syncs

    def evaluate_scenario(
        self,
        request: CounterfactualScenarioRequest,
        inference_service: Any,
    ) -> CounterfactualScenarioResponse:
        """Executes full multi-horizon counterfactual inference pipeline and delta comparison."""
        start_time = time.perf_counter()

        if not inference_service.is_loaded:
            inference_service._try_load()

        # 1. Validate perturbations
        self.validate_perturbations(request.perturbations, request.perturbation_modes)

        # 2. Establish 37-D baseline vector
        if request.baseline_vector is not None:
            baseline_raw = np.array(request.baseline_vector, dtype=np.float32)
            validate_feature_vector(baseline_raw)
            if baseline_raw.ndim == 1:
                baseline_raw = baseline_raw.reshape(1, -1)
        elif request.baseline_features is not None:
            vec_list = [0.0] * 37
            for k, v in request.baseline_features.items():
                if k in FEATURE_NAME_TO_INDEX:
                    vec_list[FEATURE_NAME_TO_INDEX[k]] = float(v)
            baseline_raw = np.array(vec_list, dtype=np.float32).reshape(1, -1)
        else:
            baseline_raw = self.get_default_baseline_vector(inference_service)


        # 3. Build Counterfactual Vector
        cf_raw, applied_perturbations = self.compute_counterfactual_vector(
            baseline_vector=baseline_raw,
            perturbations=request.perturbations,
            perturbation_modes=request.perturbation_modes,
            recompute_derived=request.recompute_derived,
        )

        # 4. Scale both vectors using the trained RobustScaler
        scaled_base = inference_service.scaler.transform(baseline_raw)
        scaled_cf = inference_service.scaler.transform(cf_raw)

        # 5. Multi-Horizon Comparative Re-Inference
        target_horizons = request.horizons or [5, 15, 30, 60]
        horizon_results: Dict[str, HorizonCounterfactualResult] = {}
        any_flipped = False
        max_reduction = 0.0
        max_elevation = 0.0

        for h in target_horizons:
            if h not in inference_service.HORIZONS:
                continue

            model = inference_service.horizon_models.get(h)
            calibrator = inference_service.horizon_calibrators.get(h)
            conformal_pred = inference_service.horizon_conformal.get(h)
            threshold = float(inference_service.horizon_thresholds.get(h, 0.50))

            if not model:
                continue

            # Baseline inference
            p_base_raw = float(model.predict_proba(scaled_base)[:, 1][0])
            p_base_cal = float(calibrator.predict_proba(np.array([p_base_raw]))[0]) if calibrator else p_base_raw
            p_base_cal = float(np.clip(p_base_cal, 0.0, 1.0))
            alert_base = bool(p_base_cal >= threshold)

            # Conformal set baseline
            if conformal_pred and conformal_pred.is_calibrated:
                conf_set_base = conformal_pred.predict_set(p_base_cal).prediction_set
            else:
                conf_set_base = [1] if alert_base else [0]

            # Uncertainty baseline
            p_norm_base = abs(p_base_cal - 0.5) * 2.0
            unc_base = float(np.clip((1.0 - p_norm_base) * 0.7 + (0.3 if len(conf_set_base) == 2 else 0.0), 0.0, 1.0))

            # Counterfactual inference
            p_cf_raw = float(model.predict_proba(scaled_cf)[:, 1][0])
            p_cf_cal = float(calibrator.predict_proba(np.array([p_cf_raw]))[0]) if calibrator else p_cf_raw
            p_cf_cal = float(np.clip(p_cf_cal, 0.0, 1.0))
            alert_cf = bool(p_cf_cal >= threshold)

            # Conformal set counterfactual
            if conformal_pred and conformal_pred.is_calibrated:
                conf_set_cf = conformal_pred.predict_set(p_cf_cal).prediction_set
            else:
                conf_set_cf = [1] if alert_cf else [0]

            # Uncertainty counterfactual
            p_norm_cf = abs(p_cf_cal - 0.5) * 2.0
            unc_cf = float(np.clip((1.0 - p_norm_cf) * 0.7 + (0.3 if len(conf_set_cf) == 2 else 0.0), 0.0, 1.0))

            # Delta metrics
            prob_delta = round(p_cf_cal - p_base_cal, 4)

            # Decision flip
            if alert_base and not alert_cf:
                flip_status = DecisionFlipEnum.ALERT_TO_NO_ALERT.value
                any_flipped = True
            elif not alert_base and alert_cf:
                flip_status = DecisionFlipEnum.NO_ALERT_TO_ALERT.value
                any_flipped = True
            else:
                flip_status = DecisionFlipEnum.NO_CHANGE.value

            if prob_delta < 0 and abs(prob_delta) > max_reduction:
                max_reduction = abs(prob_delta)
            elif prob_delta > 0 and prob_delta > max_elevation:
                max_elevation = prob_delta

            # Conformal transition string
            base_set_str = "{" + ", ".join(str(x) for x in conf_set_base) + "}"
            cf_set_str = "{" + ", ".join(str(x) for x in conf_set_cf) + "}"
            conformal_transition = f"{base_set_str} -> {cf_set_str}"

            # 6. TreeSHAP Attribution Diff (Step 5 Explainer Integration)
            shap_deltas: List[ShapDeltaItem] = []
            top_inc_features: List[str] = []
            top_dec_features: List[str] = []

            if request.include_shap and inference_service.shap_explainer:
                try:
                    shap_dict_base = inference_service.shap_explainer.explain_instance(
                        scaled_features=scaled_base,
                        raw_features=baseline_raw,
                        horizon_minutes=h,
                        calibrated_probability=p_base_cal,
                        raw_probability=p_base_raw,
                        top_k=5,
                    )
                    shap_dict_cf = inference_service.shap_explainer.explain_instance(
                        scaled_features=scaled_cf,
                        raw_features=cf_raw,
                        horizon_minutes=h,
                        calibrated_probability=p_cf_cal,
                        raw_probability=p_cf_raw,
                        top_k=5,
                    )

                    # Map of all attributions
                    base_attributions = {
                        c["feature_name"]: float(c.get("shap_value", 0.0))
                        for c in shap_dict_base.get("all_attributions", [])
                    }
                    cf_attributions = {
                        c["feature_name"]: float(c.get("shap_value", 0.0))
                        for c in shap_dict_cf.get("all_attributions", [])
                    }

                    # Compute attribution diff for all 37 features
                    all_diffs = []
                    for f_name in FEATURE_NAMES:
                        idx = FEATURE_NAME_TO_INDEX[f_name]
                        phi_b = base_attributions.get(f_name, 0.0)
                        phi_c = cf_attributions.get(f_name, 0.0)
                        d_phi = phi_c - phi_b

                        if d_phi > 0.001:
                            dir_str = "INCREASED_RISK_SENSITIVITY"
                        elif d_phi < -0.001:
                            dir_str = "DECREASED_RISK_SENSITIVITY"
                        else:
                            dir_str = "NEUTRAL"

                        item = ShapDeltaItem(
                            feature_name=f_name,
                            feature_index=idx,
                            baseline_shap=round(phi_b, 4),
                            counterfactual_shap=round(phi_c, 4),
                            delta_shap=round(d_phi, 4),
                            direction=dir_str,
                            baseline_observed=round(float(baseline_raw[0, idx]), 4),
                            counterfactual_observed=round(float(cf_raw[0, idx]), 4),
                            unit=FEATURE_CONSTRAINTS.get(f_name).unit if FEATURE_CONSTRAINTS.get(f_name) else None,
                        )
                        all_diffs.append(item)

                    # Sort by absolute delta
                    all_diffs.sort(key=lambda x: abs(x.delta_shap), reverse=True)
                    shap_deltas = all_diffs[:8]  # Top 8 most shifted attributions

                    top_inc_features = [d.feature_name for d in all_diffs if d.delta_shap > 0.005][:3]
                    top_dec_features = [d.feature_name for d in all_diffs if d.delta_shap < -0.005][:3]

                except Exception as e:
                    logger.warning(f"Failed to compute TreeSHAP diff for horizon +{h}m: {e}")

            unc_level_base = "AMBIGUOUS" if len(conf_set_base) == 2 else ("HIGH" if unc_base >= 0.6 else ("MEDIUM" if unc_base >= 0.3 else "LOW"))
            unc_level_cf = "AMBIGUOUS" if len(conf_set_cf) == 2 else ("HIGH" if unc_cf >= 0.6 else ("MEDIUM" if unc_cf >= 0.3 else "LOW"))

            horizon_results[str(h)] = HorizonCounterfactualResult(
                horizon_minutes=h,
                baseline_probability=round(p_base_cal, 4),
                counterfactual_probability=round(p_cf_cal, 4),
                probability_delta=prob_delta,
                baseline_alert=alert_base,
                counterfactual_alert=alert_cf,
                decision_flip=flip_status,
                decision_threshold=round(threshold, 4),
                baseline_conformal_set=conf_set_base,
                counterfactual_conformal_set=conf_set_cf,
                conformal_set_transition=conformal_transition,
                baseline_uncertainty_score=round(unc_base, 4),
                counterfactual_uncertainty_score=round(unc_cf, 4),
                baseline_uncertainty_level=unc_level_base,
                counterfactual_uncertainty_level=unc_level_cf,
                shap_deltas=shap_deltas,
                top_increased_risk_features=top_inc_features,
                top_decreased_risk_features=top_dec_features,
            )

        exec_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        scenario_id = f"cf-{uuid.uuid4().hex[:12]}"
        scenario_title = request.scenario_name or f"What-If Simulation ({len(applied_perturbations)} perturbed features)"

        # Summaries
        base_summary = {FEATURE_NAMES[i]: round(float(baseline_raw[0, i]), 4) for i in range(37)}
        cf_summary = {FEATURE_NAMES[i]: round(float(cf_raw[0, i]), 4) for i in range(37)}

        response = CounterfactualScenarioResponse(
            scenario_id=scenario_id,
            scenario_name=scenario_title,
            description=request.description,
            timestamp=datetime.now(timezone.utc),
            scientific_disclaimer=(
                "Measures model prediction sensitivity to perturbed feature inputs under frozen model weights. "
                "This is not a physical causal counterfactual or causal intervention analysis."
            ),
            model_version=inference_service.model_version,
            applied_perturbations=applied_perturbations,
            horizon_results=horizon_results,
            any_decision_flipped=any_flipped,
            max_risk_reduction=round(max_reduction, 4),
            max_risk_elevation=round(max_elevation, 4),
            execution_latency_ms=exec_ms,
            baseline_vector_summary=base_summary,
            counterfactual_vector_summary=cf_summary,
        )

        # 7. Audit log persistence
        self.log_scenario(response)

        return response

    def log_scenario(self, scenario_resp: CounterfactualScenarioResponse) -> None:
        """Appends scenario evaluation to in-memory ring buffer audit log."""
        self._scenario_history.append(scenario_resp)
        self._scenario_lookup[scenario_resp.scenario_id] = scenario_resp

    def get_recent_scenarios(self, limit: int = 20) -> List[CounterfactualScenarioResponse]:
        """Retrieves list of recently evaluated what-if scenarios."""
        items = list(self._scenario_history)
        items.reverse()
        return items[:limit]

    def get_scenario_by_id(self, scenario_id: str) -> Optional[CounterfactualScenarioResponse]:
        """Retrieves a specific evaluated scenario from audit storage."""
        return self._scenario_lookup.get(scenario_id)


# Global Singleton Instance
counterfactual_engine = CounterfactualEngine()
