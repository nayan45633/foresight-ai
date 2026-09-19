"""Foresight AI - Model Registry & Calibration Schemas (Step 4)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HorizonCalibrationSummary(BaseModel):
    horizon_minutes: int
    calibration_method: str
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: Optional[float] = None
    log_loss: Optional[float] = None
    status: str
    conformal_target_coverage: Optional[float] = None
    conformal_empirical_coverage: Optional[float] = None
    conformal_average_set_size: Optional[float] = None


class ModelStatusResponse(BaseModel):
    version_tag: str
    model_architecture: str
    status: str
    is_active: bool
    brier_score: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    f1_score: Optional[float] = None
    supported_horizons: List[int] = [5, 15, 30, 60]
    loaded_at: datetime
    hyperparameters: Dict[str, Any] = {}
    conformal_target_coverage: float = 0.90
    horizons_summary: Dict[str, HorizonCalibrationSummary] = {}


class CalibrationMetricsResponse(BaseModel):
    model_version: str
    brier_score: float
    expected_calibration_error: float
    reliability_diagram_bins: List[Dict[str, Any]]
    evaluated_samples_count: int
    last_calibrated_at: datetime
    conformal_target_coverage: float = 0.90
    conformal_empirical_coverage: Optional[float] = None
    conformal_average_set_size: Optional[float] = None
    per_horizon_metrics: Dict[str, HorizonCalibrationSummary] = {}


class ExplainRequest(BaseModel):
    horizon_minutes: int = Field(default=15, description="Forecasting horizon (5, 15, 30, 60)")
    top_k: int = Field(default=5, ge=1, le=20, description="Top positive and negative contributors count")


class FeatureAttributionSchema(BaseModel):
    feature_name: str
    feature_index: int
    observed_value: float
    scaled_value: float
    unit: Optional[str] = None
    source: str
    shap_value: float
    absolute_magnitude: float
    direction: str
    description: str
    feature_description: str
    rank: Optional[int] = None


class ExplainResponse(BaseModel):
    horizon_minutes: int
    status: str
    model_version: str
    schema_version: str
    calibrated_probability: float
    raw_probability: Optional[float] = None
    raw_margin: float
    base_value: float
    top_positive_contributors: List[FeatureAttributionSchema]
    top_negative_contributors: List[FeatureAttributionSchema]
    additivity_verified: bool
    additivity_delta: Optional[float] = None
    computation_latency_ms: float


class GlobalFeatureImportanceItem(BaseModel):
    feature_name: str
    feature_index: int
    mean_abs_shap: float
    unit: Optional[str] = None
    description: str
    rank: int


class HorizonMatrixRow(BaseModel):
    feature_name: str
    feature_index: int
    unit: Optional[str] = None
    description: str
    overall_mean_abs_shap: float
    shap_5m: float
    shap_15m: float
    shap_30m: float
    shap_60m: float


class GlobalExplainResponse(BaseModel):
    model_version: str
    schema_version: str
    evaluated_samples_count: int
    generated_at: str
    top_global_features: List[GlobalFeatureImportanceItem]
    horizon_comparison_matrix: List[HorizonMatrixRow]


class HorizonForecastIntelligenceSchema(BaseModel):
    horizon_minutes: int
    forecast_timestamp: datetime
    target_timestamp: datetime
    calibrated_probability: float
    raw_probability: Optional[float] = None
    decision_threshold: float
    binary_alert_decision: bool
    conformal_prediction_set: List[int]
    conformal_set_type: str
    conformal_target_coverage: float
    uncertainty_score: float
    uncertainty_level: str
    model_version: str
    calibration_version: str
    threat_class: str
    severity: str
    probability_delta_from_previous_horizon: Optional[float] = None
    shap_top_positive: List[FeatureAttributionSchema] = []
    shap_top_negative: List[FeatureAttributionSchema] = []
    shap_explanation_available: bool = False


class MultiHorizonTimelineResponse(BaseModel):
    forecast_timestamp: datetime
    target_entity: str
    horizons: List[HorizonForecastIntelligenceSchema]
    earliest_warning_horizon_minutes: Optional[int] = None
    max_risk_horizon_minutes: Optional[int] = None
    is_alert_active_any_horizon: bool = False
    temporal_consistency_valid: bool = True
    temporal_consistency_notes: List[str] = []
    anomaly_score: float = 0.0


class EmpiricalLeadTimeMatchSchema(BaseModel):
    match_id: str
    forecast_id: str
    forecast_timestamp: datetime
    horizon_minutes: int
    forecast_probability: float
    decision_threshold: float
    actual_event_id: str
    actual_event_timestamp: datetime
    actual_threat_type: str
    empirical_lead_time_minutes: float
    is_earliest_warning_for_event: bool


class LeadTimeScorecardResponse(BaseModel):
    evaluation_period_start: Optional[datetime] = None
    evaluation_period_end: Optional[datetime] = None
    status: str
    status_message: str
    mean_lead_time_minutes: Optional[float] = None
    median_lead_time_minutes: Optional[float] = None
    min_lead_time_minutes: Optional[float] = None
    max_lead_time_minutes: Optional[float] = None
    std_lead_time_minutes: Optional[float] = None
    total_emitted_forecasts: int
    total_attack_events: int
    valid_forecast_event_matches: int
    missed_attack_events: int
    false_early_warnings: int
    unmatched_forecasts: int
    empirical_forecast_coverage_rate: Optional[float] = None
    earliest_warning_horizon_distribution: Dict[str, int]
    matches: List[EmpiricalLeadTimeMatchSchema]


class ModelVersionRecordSchema(BaseModel):
    id: str
    version_tag: str
    model_architecture: str
    status: str
    feature_schema_version: str
    calibration_version: str
    conformal_version: str
    brier_score: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    f1_score: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    roc_auc_score: Optional[float] = None
    conformal_target_coverage: float
    conformal_empirical_coverage: Optional[float] = None
    hyperparameters: Dict[str, Any] = {}
    metrics_summary: Dict[str, Any] = {}
    artifact_path: Optional[str] = None
    description: Optional[str] = None
    trained_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelVersionCreateSchema(BaseModel):
    version_tag: str
    model_architecture: str
    feature_schema_version: str = "v1.0.0"
    calibration_version: str = "v1.0.0"
    conformal_version: str = "v1.0.0"
    brier_score: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    f1_score: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    roc_auc_score: Optional[float] = None
    conformal_target_coverage: float = 0.90
    conformal_empirical_coverage: Optional[float] = None
    hyperparameters: Dict[str, Any] = {}
    metrics_summary: Dict[str, Any] = {}
    artifact_path: Optional[str] = None
    description: Optional[str] = None


