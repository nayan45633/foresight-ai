"""Foresight AI - Authoritative Feature Schema Definition (Step 5).

Defines the exact, versioned 37-dimensional input feature schema:
- 28 Base Window Telemetry Features (Indices 0..27)
- 8 Rolling Temporal Derivatives (Indices 28..35)
- 1 Unsupervised Isolation Forest Behavioral Anomaly Score (Index 36)

Provides feature metadata, descriptions, units, human-readable explanation templates,
and rigorous input validation.
"""

from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass(frozen=True)
class FeatureDefinition:
    """Metadata specification for a single input feature."""
    index: int
    name: str
    datatype: str
    unit: Optional[str]
    source: str
    description: str
    interpretation_template_positive: str
    interpretation_template_negative: str
    preprocessing: str = "RobustScaler"

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def category(self) -> str:
        if self.index <= 3:
            return "volume"
        elif self.index <= 7:
            return "duration"
        elif self.index <= 12:
            return "tcp_flags"
        elif self.index <= 18:
            return "entropy"
        elif self.index <= 27:
            return "protocol"
        elif self.index <= 35:
            return "temporal_delta"
        else:
            return "anomaly"

    @property
    def positive_risk_meaning(self) -> str:
        return self.interpretation_template_positive

    @property
    def negative_risk_meaning(self) -> str:
        return self.interpretation_template_negative



# 37 Authoritative Feature Definitions
FEATURE_DEFINITIONS: List[FeatureDefinition] = [
    # --------------------------------------------------------------------------
    # 1. Base Window Telemetry Features (0..27)
    # --------------------------------------------------------------------------
    FeatureDefinition(
        index=0,
        name="flow_volume",
        datatype="float32",
        unit="flows/window",
        source="window_aggregator",
        description="Total distinct network bidirectional flows active in observation window",
        interpretation_template_positive="Elevated total active flow volume increased the model's attack-risk score.",
        interpretation_template_negative="Low or nominal active flow volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=1,
        name="packet_volume",
        datatype="float32",
        unit="packets/window",
        source="window_aggregator",
        description="Total aggregate packet count across all flows in observation window",
        interpretation_template_positive="High aggregate packet volume increased the model's attack-risk score.",
        interpretation_template_negative="Nominal packet volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=2,
        name="byte_volume",
        datatype="float32",
        unit="bytes/window",
        source="window_aggregator",
        description="Total aggregate payload and header bytes transferred in observation window",
        interpretation_template_positive="Heavy aggregate byte volume increased the model's attack-risk score.",
        interpretation_template_negative="Low byte volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=3,
        name="packets_per_second",
        datatype="float32",
        unit="packets/s",
        source="feature_extractor",
        description="Mean packet transmission rate across the window duration",
        interpretation_template_positive="High packet transmission rate increased the model's attack-risk score.",
        interpretation_template_negative="Baseline packet rate decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=4,
        name="bytes_per_second",
        datatype="float32",
        unit="bytes/s",
        source="feature_extractor",
        description="Mean volumetric byte throughput across the window duration",
        interpretation_template_positive="Elevated byte throughput rate increased the model's attack-risk score.",
        interpretation_template_negative="Baseline byte throughput decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=5,
        name="mean_flow_duration_ms",
        datatype="float32",
        unit="ms",
        source="feature_extractor",
        description="Average flow connection duration in milliseconds",
        interpretation_template_positive="Abnormal average flow duration increased the model's attack-risk score.",
        interpretation_template_negative="Standard flow duration decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=6,
        name="duration_variance",
        datatype="float32",
        unit="ms²",
        source="feature_extractor",
        description="Statistical variance of connection lifetimes across flows in the window",
        interpretation_template_positive="High flow lifetime variance increased the model's attack-risk score.",
        interpretation_template_negative="Uniform connection lifetimes decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=7,
        name="forward_packets_total",
        datatype="float32",
        unit="packets",
        source="feature_extractor",
        description="Total client-to-server (forward) packets transmitted",
        interpretation_template_positive="High forward packet count increased the model's attack-risk score.",
        interpretation_template_negative="Nominal forward packet volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=8,
        name="backward_packets_total",
        datatype="float32",
        unit="packets",
        source="feature_extractor",
        description="Total server-to-client (backward) response packets transmitted",
        interpretation_template_positive="Asymmetric backward packet volume increased the model's attack-risk score.",
        interpretation_template_negative="Balanced backward response volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=9,
        name="forward_bytes_total",
        datatype="float32",
        unit="bytes",
        source="feature_extractor",
        description="Total client-to-server outbound bytes transferred",
        interpretation_template_positive="Heavy outbound forward byte transfer increased the model's attack-risk score.",
        interpretation_template_negative="Baseline forward byte transfer decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=10,
        name="backward_bytes_total",
        datatype="float32",
        unit="bytes",
        source="feature_extractor",
        description="Total server-to-client inbound response bytes transferred",
        interpretation_template_positive="High inbound byte volume increased the model's attack-risk score.",
        interpretation_template_negative="Nominal inbound byte volume decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=11,
        name="forward_backward_ratio",
        datatype="float32",
        unit="ratio",
        source="feature_extractor",
        description="Ratio of forward to backward packets; high ratios indicate unidirectional traffic",
        interpretation_template_positive="Asymmetric forward-to-backward packet ratio increased the model's attack-risk score.",
        interpretation_template_negative="Symmetric forward-to-backward packet ratio decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=12,
        name="mean_packet_length",
        datatype="float32",
        unit="bytes/packet",
        source="feature_extractor",
        description="Mean packet length in bytes across all flows in the window",
        interpretation_template_positive="Unusual mean packet size increased the model's attack-risk score.",
        interpretation_template_negative="Standard mean packet size decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=13,
        name="packet_length_std",
        datatype="float32",
        unit="bytes",
        source="feature_extractor",
        description="Standard deviation of packet lengths in bytes",
        interpretation_template_positive="Uniform or fixed packet size dispersion increased the model's attack-risk score.",
        interpretation_template_negative="Natural packet length variance decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=14,
        name="syn_count",
        datatype="float32",
        unit="packets",
        source="feature_extractor",
        description="Total TCP packets with SYN flag set in observation window",
        interpretation_template_positive="High TCP SYN packet count increased the model's attack-risk score.",
        interpretation_template_negative="Low TCP SYN packet count decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=15,
        name="syn_rate",
        datatype="float32",
        unit="packets/s",
        source="feature_extractor",
        description="Rate of TCP SYN packet initiation per second",
        interpretation_template_positive="Elevated TCP SYN initiation rate increased the model's attack-risk score.",
        interpretation_template_negative="Normal TCP SYN initiation rate decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=16,
        name="ack_count",
        datatype="float32",
        unit="packets",
        source="feature_extractor",
        description="Total TCP packets with ACK flag set in observation window",
        interpretation_template_positive="Low ACK relative to SYN increased the model's attack-risk score.",
        interpretation_template_negative="Healthy TCP ACK count decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=17,
        name="rst_count",
        datatype="float32",
        unit="packets",
        source="feature_extractor",
        description="Total TCP connection reset (RST) packets observed",
        interpretation_template_positive="Elevated TCP RST packet count increased the model's attack-risk score.",
        interpretation_template_negative="Minimal TCP RST occurrences decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=18,
        name="syn_ack_ratio",
        datatype="float32",
        unit="ratio",
        source="feature_extractor",
        description="Ratio of SYN packets to ACK packets; ratio > 1 indicates incomplete handshakes",
        interpretation_template_positive="High SYN-to-ACK imbalance increased the model's attack-risk score.",
        interpretation_template_negative="Balanced SYN-to-ACK handshake ratio decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=19,
        name="rst_ratio",
        datatype="float32",
        unit="ratio",
        source="feature_extractor",
        description="Proportion of flows terminated abnormally with RST flags",
        interpretation_template_positive="Elevated TCP reset ratio increased the model's attack-risk score.",
        interpretation_template_negative="Nominal TCP reset ratio decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=20,
        name="unique_source_ips",
        datatype="float32",
        unit="count",
        source="feature_extractor",
        description="Count of unique source IP addresses active in window",
        interpretation_template_positive="Dispersion in unique source IP addresses increased the model's attack-risk score.",
        interpretation_template_negative="Stable source IP cardinality decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=21,
        name="unique_destination_ips",
        datatype="float32",
        unit="count",
        source="feature_extractor",
        description="Count of unique destination IP addresses targeted in window",
        interpretation_template_positive="Broad destination IP targeting increased the model's attack-risk score.",
        interpretation_template_negative="Standard destination IP cardinality decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=22,
        name="unique_source_ports",
        datatype="float32",
        unit="count",
        source="feature_extractor",
        description="Count of unique ephemeral source ports observed",
        interpretation_template_positive="Ephemeral source port randomization increased the model's attack-risk score.",
        interpretation_template_negative="Nominal source port usage decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=23,
        name="unique_destination_ports",
        datatype="float32",
        unit="count",
        source="feature_extractor",
        description="Count of unique destination service ports accessed",
        interpretation_template_positive="Broad destination service port scanning increased the model's attack-risk score.",
        interpretation_template_negative="Focused service port usage decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=24,
        name="entropy_source_ips",
        datatype="float32",
        unit="bits",
        source="feature_extractor",
        description="Shannon entropy of source IP distribution: H(X) = -sum(p * log2(p))",
        interpretation_template_positive="Elevated source IP address entropy increased the model's attack-risk score.",
        interpretation_template_negative="Low source IP address entropy decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=25,
        name="entropy_dest_ips",
        datatype="float32",
        unit="bits",
        source="feature_extractor",
        description="Shannon entropy of destination IP distribution",
        interpretation_template_positive="High destination IP address entropy increased the model's attack-risk score.",
        interpretation_template_negative="Concentrated destination IP address entropy decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=26,
        name="entropy_source_ports",
        datatype="float32",
        unit="bits",
        source="feature_extractor",
        description="Shannon entropy of source port distribution",
        interpretation_template_positive="High source port distribution entropy increased the model's attack-risk score.",
        interpretation_template_negative="Nominal source port entropy decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=27,
        name="entropy_dest_ports",
        datatype="float32",
        unit="bits",
        source="feature_extractor",
        description="Shannon entropy of destination port distribution",
        interpretation_template_positive="Dispersed destination port entropy increased the model's attack-risk score.",
        interpretation_template_negative="Concentrated destination port entropy decreased the model's attack-risk score.",
    ),

    # --------------------------------------------------------------------------
    # 2. Rolling Temporal Derivatives (28..35)
    # --------------------------------------------------------------------------
    FeatureDefinition(
        index=28,
        name="delta_packet_rate",
        datatype="float32",
        unit="packets/s",
        source="dataset_builder",
        description="Step change in packet rate relative to previous temporal window",
        interpretation_template_positive="Sudden positive surge in packet rate increased the model's attack-risk score.",
        interpretation_template_negative="Steady or declining packet rate decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=29,
        name="packet_rate_slope",
        datatype="float32",
        unit="packets/s²",
        source="dataset_builder",
        description="First-order linear regression slope of packet rates over past k windows",
        interpretation_template_positive="Upward accelerating packet rate trajectory increased the model's attack-risk score.",
        interpretation_template_negative="Flat or decreasing packet rate trajectory decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=30,
        name="delta_byte_rate",
        datatype="float32",
        unit="bytes/s",
        source="dataset_builder",
        description="Step change in byte throughput relative to previous temporal window",
        interpretation_template_positive="Sudden increase in volumetric byte throughput increased the model's attack-risk score.",
        interpretation_template_negative="Stable byte throughput rate decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=31,
        name="entropy_change_dest_ports",
        datatype="float32",
        unit="bits",
        source="dataset_builder",
        description="Rate of change in destination port entropy across temporal windows",
        interpretation_template_positive="Rapidly expanding destination port dispersion increased the model's attack-risk score.",
        interpretation_template_negative="Stable destination port entropy decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=32,
        name="entropy_change_src_ips",
        datatype="float32",
        unit="bits",
        source="dataset_builder",
        description="Rate of change in source IP entropy across temporal windows",
        interpretation_template_positive="Rapid change in source IP diversity increased the model's attack-risk score.",
        interpretation_template_negative="Stable source IP distribution decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=33,
        name="syn_rate_acceleration",
        datatype="float32",
        unit="packets/s²",
        source="dataset_builder",
        description="Second derivative / acceleration of TCP SYN initiation rate",
        interpretation_template_positive="Accelerating TCP SYN arrival rate increased the model's attack-risk score.",
        interpretation_template_negative="Non-accelerating TCP SYN rate decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=34,
        name="burst_score_delta",
        datatype="float32",
        unit="ratio",
        source="dataset_builder",
        description="Change in peak-to-mean traffic burstiness ratio across temporal windows",
        interpretation_template_positive="Sharply increasing volumetric burstiness ratio increased the model's attack-risk score.",
        interpretation_template_negative="Stable or declining burstiness ratio decreased the model's attack-risk score.",
    ),
    FeatureDefinition(
        index=35,
        name="dest_concentration_delta",
        datatype="float32",
        unit="ratio",
        source="dataset_builder",
        description="Rate of change in traffic destination concentration ratio",
        interpretation_template_positive="Shifting destination concentration ratio increased the model's attack-risk score.",
        interpretation_template_negative="Stable destination concentration ratio decreased the model's attack-risk score.",
    ),

    # --------------------------------------------------------------------------
    # 3. Unsupervised Behavioral Anomaly Score (36)
    # --------------------------------------------------------------------------
    FeatureDefinition(
        index=36,
        name="behavioral_anomaly_score",
        datatype="float32",
        unit="score [0.0, 1.0]",
        source="anomaly_detector",
        description="Unsupervised Isolation Forest perimeter deviation score relative to nominal traffic",
        interpretation_template_positive="High unsupervised perimeter anomaly deviation increased the model's attack-risk score.",
        interpretation_template_negative="Nominal unsupervised behavioral score decreased the model's attack-risk score.",
    ),
]

FEATURE_NAME_TO_INDEX: Dict[str, int] = {f.name: f.index for f in FEATURE_DEFINITIONS}
FEATURE_INDEX_TO_DEF: Dict[int, FeatureDefinition] = {f.index: f for f in FEATURE_DEFINITIONS}
FEATURE_SCHEMA: List[FeatureDefinition] = FEATURE_DEFINITIONS
FEATURE_SCHEMA_BY_NAME: Dict[str, int] = FEATURE_NAME_TO_INDEX
FEATURE_NAMES: List[str] = [f.name for f in FEATURE_DEFINITIONS]
SCHEMA_VERSION: str = "v1.0.0"


def get_feature_names() -> List[str]:
    """Returns authoritative ordered list of 37 feature names."""
    return [f.name for f in FEATURE_DEFINITIONS]


def get_ordered_feature_names() -> List[str]:
    """Returns authoritative ordered list of 37 feature names."""
    return [f.name for f in FEATURE_DEFINITIONS]


def get_feature_explanation_template(feature_name: str, feature_value: float, shap_value: float) -> str:
    """Formats human-readable explanation template with dynamic value interpolation."""
    idx = FEATURE_NAME_TO_INDEX.get(feature_name)
    if idx is None:
        direction = "increased" if shap_value > 0 else "reduced"
        return f"Feature '{feature_name}' (value {feature_value:.2f}) {direction} the attack forecast risk."

    feat_def = FEATURE_INDEX_TO_DEF[idx]
    base_template = feat_def.interpretation_template_positive if shap_value > 0 else feat_def.interpretation_template_negative
    val_str = f"{feature_value:.2f} {feat_def.unit or ''}".strip()
    return f"{base_template} (Observed: {val_str}, SHAP margin impact: {shap_value:+.4f})"



def validate_feature_vector(vec: np.ndarray) -> np.ndarray:
    """Validates that a feature vector matches schema dimension, finiteness, and dtype."""
    if not isinstance(vec, np.ndarray):
        vec = np.array(vec, dtype=np.float32)

    if vec.ndim == 1:
        if len(vec) != 37:
            raise ValueError(f"Feature vector must have exactly 37 elements, got {len(vec)}")
        if not np.all(np.isfinite(vec)):
            raise ValueError("Feature vector contains non-finite values (NaN or Inf)")
        return vec.reshape(1, -1)
    elif vec.ndim == 2:
        if vec.shape[1] != 37:
            raise ValueError(f"Feature matrix must have 37 columns, got shape {vec.shape}")
        if not np.all(np.isfinite(vec)):
            raise ValueError("Feature matrix contains non-finite values (NaN or Inf)")
        return vec
    else:
        raise ValueError(f"Feature input must be 1D or 2D array, got ndim={vec.ndim}")


def export_feature_schema_json(output_path: str = "./artifacts/metadata/feature_schema_v1.json") -> str:
    """Serializes feature schema specification to JSON metadata file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    schema_dict = {
        "schema_version": SCHEMA_VERSION,
        "feature_count": len(FEATURE_DEFINITIONS),
        "features": [asdict(f) for f in FEATURE_DEFINITIONS],
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(schema_dict, fh, indent=2)
    return output_path
