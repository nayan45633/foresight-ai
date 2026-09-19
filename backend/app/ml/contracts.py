"""Foresight AI - Machine Learning & Telemetry Data Contracts.

Strict Pydantic schemas defining the mathematical, statistical, and temporal contracts
between data ingestion, feature engineering, ML inference, uncertainty quantification,
and explainability.
"""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ml.feature_schema import FEATURE_NAMES, get_feature_names


class ProtocolEnum(str, Enum):
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    GRE = "GRE"
    OTHER = "OTHER"


class FlowDirectionEnum(str, Enum):
    INGRESS = "ingress"
    EGRESS = "egress"
    INTERNAL = "internal"


class ThreatSeverityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ==============================================================================
# 1. NORMALIZED INGESTION CONTRACT
# ==============================================================================

class FlowRecord(BaseModel):
    """Normalized internal flow representation.
    
    Accommodates heterogeneous telemetry sources (NetFlow, IPFIX, sFlow, Zeek, PCAP)
    via normalization adapters.
    """
    id: Optional[str] = Field(default=None, description="Deterministic flow fingerprint or UUID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of flow start")
    end_timestamp: Optional[datetime] = Field(default=None, description="UTC timestamp of flow end")
    source_ip: str = Field(..., min_length=1, max_length=45, description="IPv4 or IPv6 source address")
    destination_ip: str = Field(..., min_length=1, max_length=45, description="IPv4 or IPv6 destination address")
    source_port: int = Field(..., ge=0, le=65535, description="Source transport port")
    destination_port: int = Field(..., ge=0, le=65535, description="Destination transport port")
    protocol: ProtocolEnum = Field(default=ProtocolEnum.TCP, description="Layer 4 Protocol")
    
    # Volumetric and Rate Metrics
    flow_duration_ms: float = Field(default=0.0, ge=0.0, description="Flow duration in milliseconds")
    packet_count: int = Field(default=1, ge=0, description="Total packets in flow")
    byte_count: int = Field(default=0, ge=0, description="Total bytes in flow")
    packet_rate: Optional[float] = Field(default=None, ge=0.0, description="Packets per second")
    byte_rate: Optional[float] = Field(default=None, ge=0.0, description="Bytes per second")
    
    # Bidirectional Flow Attributes
    forward_packets: int = Field(default=0, ge=0, description="Packets sent in forward direction")
    backward_packets: int = Field(default=0, ge=0, description="Packets sent in backward direction")
    forward_bytes: int = Field(default=0, ge=0, description="Bytes sent in forward direction")
    backward_bytes: int = Field(default=0, ge=0, description="Bytes sent in backward direction")
    
    # TCP Flags & Protocol State
    tcp_flags: Optional[str] = Field(default="", description="TCP flags string (SYN, ACK, FIN, RST, PSH, URG)")
    connection_state: Optional[str] = Field(default="UNKNOWN", description="Connection state machine status")
    direction: FlowDirectionEnum = Field(default=FlowDirectionEnum.INGRESS)
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible telemetry metadata")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("packet_rate", mode="before")
    @classmethod
    def compute_packet_rate_if_missing(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None:
            return v
        return None


# ==============================================================================
# 2. TEMPORAL AGGREGATION & MATHEMATICAL FEATURE CONTRACT
# ==============================================================================

class TemporalWindowFeatures(BaseModel):
    """Rich statistical behavior features computed over a sliding temporal window."""
    window_id: str
    window_start: datetime
    window_end: datetime
    duration_seconds: int
    stride_seconds: int = 30
    target_entity: str = "GLOBAL_PERIMETER"
    
    # 1. Traffic Rates & Volumes
    flow_volume: int = 0
    packet_volume: int = 0
    byte_volume: int = 0
    packets_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # 2. Flow Duration Statistics
    mean_flow_duration_ms: float = 0.0
    duration_variance: float = 0.0
    
    # 3. Directional Statistics
    forward_packets_total: int = 0
    backward_packets_total: int = 0
    forward_bytes_total: int = 0
    backward_bytes_total: int = 0
    forward_backward_ratio: float = 1.0
    
    # 4. Packet Length Statistics
    mean_packet_length: float = 0.0
    packet_length_std: float = 0.0
    min_packet_length: float = 0.0
    max_packet_length: float = 0.0
    
    # 5. TCP Flag Behavior
    syn_count: int = 0
    syn_rate: float = 0.0
    ack_count: int = 0
    ack_rate: float = 0.0
    rst_count: int = 0
    rst_rate: float = 0.0
    fin_count: int = 0
    fin_rate: float = 0.0
    syn_ack_ratio: float = 0.0
    rst_ratio: float = 0.0
    
    # 6. Entity Diversity & Dispersion
    unique_source_ips: int = 0
    unique_destination_ips: int = 0
    unique_source_ports: int = 0
    unique_destination_ports: int = 0
    
    # 7. Shannon Entropy Metrics: H(X) = -sum(p * log2(p))
    entropy_source_ips: float = 0.0
    entropy_dest_ips: float = 0.0
    entropy_source_ports: float = 0.0
    entropy_dest_ports: float = 0.0
    
    # 8. Burstiness & Dynamics
    packet_rate_variance: float = 0.0
    byte_rate_variance: float = 0.0
    traffic_burst_score: float = 0.0
    
    # 9. Connection Behavior
    new_connections_count: int = 0
    repeated_destinations_ratio: float = 0.0
    destination_concentration_score: float = 0.0
    
    # Formatted Dense Feature Vector for ML
    vector: List[float] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. FUTURE HORIZON TARGET CONTRACT (LEAKAGE-FREE ML TARGETS)
# ==============================================================================

class FutureHorizonTarget(BaseModel):
    """Supervised target representation for multi-horizon attack forecasting.
    
    Isolated strictly from feature vectors to prevent temporal data leakage.
    """
    window_id: str
    target_timestamp: datetime
    horizon_5m_threat: str = "BENIGN"
    horizon_5m_attack_occurred: bool = False
    horizon_15m_threat: str = "BENIGN"
    horizon_15m_attack_occurred: bool = False
    horizon_30m_threat: str = "BENIGN"
    horizon_30m_attack_occurred: bool = False
    horizon_60m_threat: str = "BENIGN"
    horizon_60m_attack_occurred: bool = False


class CalibrationHealthEnum(str, Enum):
    CALIBRATED = "CALIBRATED"
    WATCH = "WATCH"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"


class CalibrationMethodEnum(str, Enum):
    NONE = "NONE"
    PLATT_SIGMOID = "PLATT_SIGMOID"
    ISOTONIC = "ISOTONIC"
    BETA = "BETA"


# ==============================================================================
# 4. EXPLAINABILITY & UNCERTAINTY CONTRACTS
# ==============================================================================

class FeatureContribution(BaseModel):
    """SHAP / Attribution score for individual contributing features."""
    feature_name: str
    feature_index: Optional[int] = None
    attribution_value: Optional[float] = Field(default=None, description="Direction and magnitude of contribution (TreeSHAP value)")
    shap_value: Optional[float] = None
    baseline_value: Optional[float] = None
    observed_value: Optional[float] = None
    scaled_value: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    direction: Optional[str] = Field(default="increases_risk", description="increases_risk or decreases_risk")
    rank: Optional[int] = None
    description: Optional[str] = None
    feature_description: Optional[str] = None
    absolute_magnitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context: Any) -> None:
        if self.attribution_value is None and self.shap_value is not None:
            object.__setattr__(self, "attribution_value", self.shap_value)
        elif self.shap_value is None and self.attribution_value is not None:
            object.__setattr__(self, "shap_value", self.attribution_value)
        if self.absolute_magnitude is None and self.shap_value is not None:
            object.__setattr__(self, "absolute_magnitude", abs(self.shap_value))



class HorizonShapExplanation(BaseModel):
    """Mathematically grounded multi-horizon TreeSHAP explanation."""
    horizon_minutes: int
    status: str = "EXPLAINED"
    model_version: str
    schema_version: str = "v1.0.0"
    calibrated_probability: float
    raw_probability: Optional[float] = None
    raw_margin: float = 0.0
    base_value: float = 0.0
    top_positive_contributors: List[FeatureContribution] = Field(default_factory=list)
    top_negative_contributors: List[FeatureContribution] = Field(default_factory=list)
    all_attributions: List[FeatureContribution] = Field(default_factory=list)
    additivity_verified: bool = True
    additivity_delta: Optional[float] = None
    computation_latency_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ConformalPredictionSet(BaseModel):
    """Split Conformal Prediction set providing marginal coverage under exchangeability.
    
    A label in the prediction set indicates it was not excluded by the conformal procedure
    at the chosen 1 - alpha coverage level. It is NOT an individual posterior probability.
    """
    prediction_set: List[int] = Field(default_factory=lambda: [0, 1], description="{0}, {1}, {0, 1}, or []")
    target_coverage: float = Field(default=0.90, ge=0.50, le=0.99)
    empirical_coverage: Optional[float] = None
    set_type: str = Field(
        default="UNCERTAIN_AMBIGUOUS",
        description="SINGLETON_BENIGN, SINGLETON_ATTACK, UNCERTAIN_AMBIGUOUS, HIGH_UNCERTAINTY_REJECTION",
    )

    model_config = ConfigDict(from_attributes=True)


class UncertaintyEstimate(BaseModel):
    """Scientific uncertainty quantification: calibrated probabilities, empirical bins, and conformal sets."""
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalized forecast uncertainty indicator in [0.0, 1.0]")
    conformal_prediction_set: ConformalPredictionSet = Field(default_factory=ConformalPredictionSet)
    calibration_status: CalibrationHealthEnum = Field(default=CalibrationHealthEnum.CALIBRATED)
    calibration_method: CalibrationMethodEnum = Field(default=CalibrationMethodEnum.ISOTONIC)
    
    # Backward compatibility indicators
    credible_interval_lower: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic lower uncertainty indicator")
    credible_interval_upper: float = Field(default=1.0, ge=0.0, le=1.0, description="Heuristic upper uncertainty indicator")
    confidence_level: float = Field(default=0.90, ge=0.5, le=0.99)
    epistemic_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic ambiguity proxy (not a formal epistemic decomposition)")
    aleatoric_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic anomaly proxy (not a formal aleatoric decomposition)")

    model_config = ConfigDict(from_attributes=True)


class ReliabilityBinData(BaseModel):
    """Data bin for empirical reliability diagrams."""
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_predicted_probability: float
    observed_positive_frequency: float
    absolute_calibration_error: float

    model_config = ConfigDict(from_attributes=True)


class CalibrationHealthReport(BaseModel):
    """Horizon-specific calibration and uncertainty health report."""
    horizon_minutes: int
    calibration_method: CalibrationMethodEnum
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: float
    log_loss: float
    status: CalibrationHealthEnum
    reliability_bins: List[ReliabilityBinData]
    conformal_target_coverage: float
    conformal_empirical_coverage: Optional[float] = None
    conformal_average_set_size: Optional[float] = None
    singleton_set_rate: Optional[float] = None
    ambiguous_set_rate: Optional[float] = None
    sample_count: int
    last_calibrated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class ForecastHorizonPrediction(BaseModel):
    """Specific forecast prediction for a given forward horizon."""
    threat: str = Field(..., description="Target threat class (e.g. DDoS, Port Scan, Exfiltration)")
    probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated threat probability")
    raw_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Uncalibrated base tree probability")
    decision_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Operational decision threshold selected on validation data")
    binary_alert_decision: bool = Field(default=False, description="Operational alert decision: true if calibrated probability >= decision threshold")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall forecast confidence score")
    horizon_minutes: int = Field(..., gt=0, description="Forecasting horizon into the future in minutes")
    severity: ThreatSeverityEnum = Field(default=ThreatSeverityEnum.LOW)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. MASTER FORECAST RESULT CONTRACT
# ==============================================================================

class ForecastResult(BaseModel):
    """Standard unified contract returned by the Foresight AI Forecasting Engine."""
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    forecast: ForecastHorizonPrediction
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized behavioral deviation score")
    uncertainty: UncertaintyEstimate
    model_version: str
    feature_contributions: List[FeatureContribution] = Field(default_factory=list)
    shap_explanation: Optional[HorizonShapExplanation] = None
    target_entity: str = "GLOBAL_PERIMETER"
    is_simulated: bool = Field(default=False, description="Flag explicitly indicating if data was generated for tests")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. MULTI-HORIZON INTELLIGENCE & TIMELINE CONTRACTS (STEP 6)
# ==============================================================================

class HorizonForecastIntelligence(BaseModel):
    """Unified forecast intelligence for a single temporal horizon (+5m, +15m, +30m, +60m)."""
    horizon_minutes: int = Field(..., description="Forward lead horizon in minutes (5, 15, 30, 60)")
    forecast_timestamp: datetime = Field(..., description="Timestamp when the forecast was emitted (NOW)")
    target_timestamp: datetime = Field(..., description="Calculated future target timestamp (forecast_timestamp + horizon_minutes)")
    calibrated_probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated threat probability")
    raw_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Uncalibrated base margin probability")
    decision_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Operational decision threshold selected on validation data")
    binary_alert_decision: bool = Field(default=False, description="True if calibrated_probability >= decision_threshold")
    conformal_prediction_set: ConformalPredictionSet = Field(default_factory=ConformalPredictionSet)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalized uncertainty indicator in [0.0, 1.0]")
    uncertainty_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH, AMBIGUOUS")
    model_version: str = "v1.0.0-temporal-gbm"
    calibration_version: str = "v1.0.0-isotonic"
    threat_class: str = "BENIGN"
    severity: ThreatSeverityEnum = ThreatSeverityEnum.LOW
    probability_delta_from_previous_horizon: Optional[float] = Field(
        default=None, description="Calibrated probability delta relative to the immediately preceding shorter horizon"
    )
    shap_top_positive: List[FeatureContribution] = Field(default_factory=list)
    shap_top_negative: List[FeatureContribution] = Field(default_factory=list)
    shap_explanation_available: bool = False

    model_config = ConfigDict(from_attributes=True)


class MultiHorizonTimeline(BaseModel):
    """Complete temporal forecast timeline from NOW across +5m, +15m, +30m, +60m."""
    forecast_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_entity: str = "GLOBAL_PERIMETER"
    horizons: List[HorizonForecastIntelligence] = Field(default_factory=list)
    earliest_warning_horizon_minutes: Optional[int] = Field(
        default=None, description="Shortest forward horizon currently triggering a binary alert"
    )
    max_risk_horizon_minutes: Optional[int] = Field(
        default=None, description="Forward horizon with the highest calibrated probability"
    )
    is_alert_active_any_horizon: bool = False
    temporal_consistency_valid: bool = True
    temporal_consistency_notes: List[str] = Field(default_factory=list)
    anomaly_score: float = 0.0

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. EMPIRICAL LEAD-TIME EVALUATION CONTRACTS (STEP 6)
# ==============================================================================

class EmpiricalLeadTimeMatch(BaseModel):
    """Detailed record of a valid forecast-to-event chronological match."""
    match_id: str
    forecast_id: str
    forecast_timestamp: datetime
    horizon_minutes: int
    forecast_probability: float
    decision_threshold: float
    actual_event_id: str
    actual_event_timestamp: datetime
    actual_threat_type: str
    empirical_lead_time_minutes: float = Field(
        ..., description="Actual observed early warning lead time: actual_event_timestamp - forecast_timestamp"
    )
    is_earliest_warning_for_event: bool = Field(
        default=False, description="True if this was the chronologically earliest alert emitted for this attack event"
    )

    model_config = ConfigDict(from_attributes=True)


class LeadTimeScorecard(BaseModel):
    """Empirical lead-time performance scorecard grounded in observed attack events."""
    evaluation_period_start: Optional[datetime] = None
    evaluation_period_end: Optional[datetime] = None
    status: str = Field(
        default="EMPIRICALLY_EVALUATED",
        description="EMPIRICALLY_EVALUATED or INSUFFICIENT_EMPIRICAL_MATCHES",
    )
    status_message: str = "Empirical lead-time metrics computed against verified attack events."
    mean_lead_time_minutes: Optional[float] = None
    median_lead_time_minutes: Optional[float] = None
    min_lead_time_minutes: Optional[float] = None
    max_lead_time_minutes: Optional[float] = None
    std_lead_time_minutes: Optional[float] = None
    total_emitted_forecasts: int = 0
    total_attack_events: int = 0
    valid_forecast_event_matches: int = 0
    missed_attack_events: int = 0
    false_early_warnings: int = 0
    unmatched_forecasts: int = 0
    empirical_forecast_coverage_rate: Optional[float] = Field(
        default=None, description="Ratio of attack events with at least one prior valid forecast alert"
    )
    earliest_warning_horizon_distribution: Dict[str, int] = Field(default_factory=dict)
    matches: List[EmpiricalLeadTimeMatch] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 8. ATTACK PATH FORECASTING & RISK STATE CONTRACTS (STEP 7)
# ==============================================================================

class AttackStageEnum(str, Enum):
    RECONNAISSANCE = "Reconnaissance"
    SCANNING = "Scanning"
    INITIAL_ACCESS = "Initial Access"
    EXECUTION = "Execution"
    PERSISTENCE = "Persistence"
    PRIVILEGE_ESCALATION = "Privilege Escalation"
    LATERAL_MOVEMENT = "Lateral Movement"
    COMMAND_AND_CONTROL = "Command & Control"
    EXFILTRATION = "Exfiltration"
    IMPACT = "Impact"
    BENIGN = "Benign/Normal"
    UNKNOWN = "Unknown"


class TransitionConfidenceStatusEnum(str, Enum):
    VALIDATED_TRANSITION = "VALIDATED_TRANSITION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BENIGN_NOMINAL = "BENIGN_NOMINAL"
    AWAITING_TELEMETRY = "AWAITING_TELEMETRY"
    POTENTIAL_UNVALIDATED = "POTENTIAL_UNVALIDATED"
    GRAPH_POSSIBLE = "GRAPH_POSSIBLE"


class RiskStateEnum(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    SUSPICIOUS = "SUSPICIOUS"
    ELEVATED = "ELEVATED"
    CRITICAL = "CRITICAL"


class AttackPathNode(BaseModel):
    """Node representing an attack stage in the directed transition graph."""
    stage: str
    is_current: bool = False
    is_predicted: bool = False
    is_forecasted: bool = False
    probability: Optional[float] = None
    evidence_strength: str = "LOW"  # LOW, MEDIUM, HIGH, VERIFIED, INSUFFICIENT_EVIDENCE, GRAPH_KNOWLEDGE_ONLY
    status: str = "POTENTIAL_UNVALIDATED"  # OBSERVED, PREDICTED, GRAPH_POSSIBLE, POTENTIAL_UNVALIDATED, INSUFFICIENT_EVIDENCE
    supporting_features: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AttackPathEdge(BaseModel):
    """Directed transition between attack stages supported by evidence or domain topology."""
    source_stage: str
    target_stage: str
    transition_probability: Optional[float] = None  # None when unvalidated / domain graph topology only
    is_forecasted: bool = False  # True ONLY when backed by a statistically supported forecast model
    transition_horizon_minutes: Optional[int] = None
    evidence_reasons: List[str] = Field(default_factory=list)
    uncertainty: str = "LOW"
    status: str = "POTENTIAL_UNVALIDATED"  # VALIDATED, GRAPH_POSSIBLE, POTENTIAL_UNVALIDATED, INSUFFICIENT_EVIDENCE

    model_config = ConfigDict(from_attributes=True)


class AttackPathForecast(BaseModel):
    """Structured contract for attack path forecasting grounded in telemetry and SHAP."""
    forecast_id: str
    forecast_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_entity: str = "GLOBAL_PERIMETER"
    current_stage: Optional[str] = None
    predicted_next_stage: Optional[str] = None
    subsequent_stages: List[str] = Field(default_factory=list)
    probability: Optional[float] = None
    uncertainty: str = "LOW"
    evidence: List[str] = Field(default_factory=list)
    supporting_features: List[Dict[str, Any]] = Field(default_factory=list)
    horizon_minutes: Optional[int] = None
    target_timestamp: Optional[datetime] = None
    transition_confidence_status: str = TransitionConfidenceStatusEnum.INSUFFICIENT_EVIDENCE.value
    model_version: str = "v1.0.0-temporal-gbm"
    graph_nodes: List[AttackPathNode] = Field(default_factory=list)
    graph_edges: List[AttackPathEdge] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RiskStateTransition(BaseModel):
    """Auditable state transition event."""
    transition_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_state: RiskStateEnum
    new_state: RiskStateEnum
    triggering_evidence: List[str] = Field(default_factory=list)
    forecast_probability: float
    anomaly_score: float
    uncertainty: str
    triggering_horizon: Optional[int] = None
    reason: str
    model_version: str

    model_config = ConfigDict(from_attributes=True)


class RiskStateEvaluation(BaseModel):
    """Deterministic evaluation of current system risk state with hysteresis tracking."""
    evaluation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_state: RiskStateEnum
    previous_state: RiskStateEnum
    state_duration_seconds: float = 0.0
    cycles_in_state: int = 1
    is_hysteresis_dampened: bool = False
    hysteresis_notes: List[str] = Field(default_factory=list)
    max_calibrated_probability: float = 0.0
    triggering_horizon_minutes: Optional[int] = None
    active_alert_horizons: List[int] = Field(default_factory=list)
    anomaly_score: float = 0.0
    conformal_coverage_status: str = "NORMAL"
    uncertainty_level: str = "LOW"
    evidence_summary: List[str] = Field(default_factory=list)
    top_risk_features: List[Dict[str, Any]] = Field(default_factory=list)
    attack_path_summary: Optional[AttackPathForecast] = None
    model_version: str = "v1.0.0-temporal-gbm"

    model_config = ConfigDict(from_attributes=True)


class RiskTimelineResponse(BaseModel):
    """Chronological risk timeline response."""
    current_evaluation: RiskStateEvaluation
    timeline_transitions: List[RiskStateTransition] = Field(default_factory=list)
    historical_evaluations: List[RiskStateEvaluation] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 8. COUNTERFACTUAL WHAT-IF & MODEL SENSITIVITY CONTRACTS (Step 8)
# ==============================================================================

class FeatureClassificationEnum(str, Enum):
    DIRECTLY_PERTURBABLE = "DIRECTLY_PERTURBABLE"
    DERIVED = "DERIVED"
    DEPENDENCY_CONSTRAINED = "DEPENDENCY_CONSTRAINED"


class PerturbationModeEnum(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RELATIVE_PERCENT = "RELATIVE_PERCENT"
    DELTA = "DELTA"


class DecisionFlipEnum(str, Enum):
    ALERT_TO_NO_ALERT = "ALERT_TO_NO_ALERT"
    NO_ALERT_TO_ALERT = "NO_ALERT_TO_ALERT"
    NO_CHANGE = "NO_CHANGE"


class FeaturePerturbationSpec(BaseModel):
    """User specification for single feature perturbation."""
    feature_name: str
    value: float
    mode: PerturbationModeEnum = PerturbationModeEnum.ABSOLUTE

    model_config = ConfigDict(from_attributes=True)


class AppliedFeaturePerturbation(BaseModel):
    """Audit of an applied feature perturbation with baseline vs counterfactual delta."""
    feature_name: str
    feature_index: int
    original_value: float
    perturbed_value: float
    mode: str
    delta: float
    delta_percent: Optional[float] = None
    classification: str
    unit: Optional[str] = None
    is_derived_auto_sync: bool = False

    model_config = ConfigDict(from_attributes=True)


class ShapDeltaItem(BaseModel):
    """Difference in TreeSHAP attribution between baseline and counterfactual instances."""
    feature_name: str
    feature_index: int
    baseline_shap: float
    counterfactual_shap: float
    delta_shap: float
    direction: str  # "INCREASED_RISK_SENSITIVITY", "DECREASED_RISK_SENSITIVITY", "NEUTRAL"
    baseline_observed: float
    counterfactual_observed: float
    unit: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HorizonCounterfactualResult(BaseModel):
    """Counterfactual inference comparison for a specific forecasting horizon (+5m, +15m, +30m, +60m)."""
    horizon_minutes: int
    baseline_probability: float
    counterfactual_probability: float
    probability_delta: float  # Delta P_h = P_cf - P_base
    baseline_alert: bool
    counterfactual_alert: bool
    decision_flip: str  # ALERT_TO_NO_ALERT, NO_ALERT_TO_ALERT, NO_CHANGE
    decision_threshold: float
    baseline_conformal_set: List[int]
    counterfactual_conformal_set: List[int]
    conformal_set_transition: str  # e.g., "{1} -> {0}", "{1} -> {0, 1}"
    baseline_uncertainty_score: float
    counterfactual_uncertainty_score: float
    baseline_uncertainty_level: str
    counterfactual_uncertainty_level: str
    shap_deltas: List[ShapDeltaItem] = Field(default_factory=list)
    top_increased_risk_features: List[str] = Field(default_factory=list)
    top_decreased_risk_features: List[str] = Field(default_factory=list)
    baseline_shap_explanation: Optional[HorizonShapExplanation] = None
    counterfactual_shap_explanation: Optional[HorizonShapExplanation] = None

    model_config = ConfigDict(from_attributes=True)


class CounterfactualScenarioRequest(BaseModel):
    """Request payload for running a Counterfactual What-If Model Sensitivity simulation."""
    scenario_name: Optional[str] = Field(default=None, description="Human-readable scenario title")
    description: Optional[str] = Field(default=None, description="Operational justification or scenario context")
    baseline_features: Optional[Dict[str, float]] = Field(default=None, description="Explicit 37-D baseline feature dictionary")
    baseline_vector: Optional[List[float]] = Field(default=None, description="Explicit 37-D baseline vector array")
    perturbations: Dict[str, float] = Field(..., description="Map of feature names to perturbed target values")
    perturbation_modes: Optional[Dict[str, PerturbationModeEnum]] = Field(default=None, description="Per-feature mode (ABSOLUTE, RELATIVE_PERCENT, DELTA)")
    recompute_derived: bool = Field(default=True, description="Automatically recompute derived ratios if constituent base features change")
    horizons: List[int] = Field(default_factory=lambda: [5, 15, 30, 60], description="Target forecasting horizons")
    include_shap: bool = Field(default=True, description="Compute TreeSHAP attribution diffs for each horizon")

    model_config = ConfigDict(from_attributes=True)


class CounterfactualScenarioResponse(BaseModel):
    """Complete response payload for a Counterfactual What-If Model Sensitivity evaluation."""
    scenario_id: str
    scenario_name: str
    description: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scientific_disclaimer: str = (
        "Measures model prediction sensitivity to perturbed feature inputs under frozen model weights. "
        "This is not a physical causal counterfactual or causal intervention analysis."
    )
    model_version: str
    applied_perturbations: List[AppliedFeaturePerturbation] = Field(default_factory=list)
    horizon_results: Dict[str, HorizonCounterfactualResult] = Field(default_factory=dict)
    any_decision_flipped: bool = False
    max_risk_reduction: float = 0.0
    max_risk_elevation: float = 0.0
    execution_latency_ms: float = 0.0
    baseline_vector_summary: Dict[str, float] = Field(default_factory=dict)
    counterfactual_vector_summary: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CounterfactualPreset(BaseModel):
    """Predefined security intervention / stress test preset."""
    preset_id: str
    title: str
    category: str
    description: str
    perturbations: Dict[str, float]
    recompute_derived: bool = True
    suggested_use_case: str

    model_config = ConfigDict(from_attributes=True)


class FeatureMetadataItem(BaseModel):
    """Detailed feature metadata, valid range, step size, and dependency classification."""
    index: int
    name: str
    display_name: str
    datatype: str
    unit: Optional[str]
    category: str
    classification: str  # DIRECTLY_PERTURBABLE, DERIVED, DEPENDENCY_CONSTRAINED
    min_value: float
    max_value: float
    default_value: float
    slider_step: float
    description: str
    positive_risk_meaning: str
    negative_risk_meaning: str

    model_config = ConfigDict(from_attributes=True)


class FeatureMetadataCatalogResponse(BaseModel):
    """Catalog of all 37 features with range constraints, units, and classifications."""
    schema_version: str = "v1.0.0"
    total_features: int = 37
    features: List[FeatureMetadataItem]
    presets: List[CounterfactualPreset]
    scientific_disclaimer: str

    model_config = ConfigDict(from_attributes=True)



