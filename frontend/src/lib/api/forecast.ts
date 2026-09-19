/**
 * Foresight AI - Forecast Intelligence API Service
 */

import { apiClient } from './client';

export interface FeatureAttributionDetail {
  feature_name: string;
  feature_index: number;
  observed_value: number;
  scaled_value: number;
  unit?: string;
  source: string;
  shap_value: number;
  absolute_magnitude: number;
  direction: 'increases_risk' | 'decreases_risk';
  description: string;
  feature_description: string;
  rank?: number;
}

export interface HorizonForecastIntelligence {
  horizon_minutes: number;
  forecast_timestamp: string;
  target_timestamp: string;
  calibrated_probability: number;
  raw_probability?: number;
  decision_threshold: number;
  binary_alert_decision: boolean;
  conformal_prediction_set: number[];
  conformal_set_type: string;
  conformal_target_coverage: number;
  uncertainty_score: number;
  uncertainty_level: string;
  model_version: string;
  calibration_version: string;
  threat_class: string;
  severity: string;
  probability_delta_from_previous_horizon?: number;
  shap_top_positive: FeatureAttributionDetail[];
  shap_top_negative: FeatureAttributionDetail[];
  shap_explanation_available: boolean;
}

export interface MultiHorizonTimelineResponse {
  forecast_timestamp: string;
  target_entity: string;
  horizons: HorizonForecastIntelligence[];
  earliest_warning_horizon_minutes?: number;
  max_risk_horizon_minutes?: number;
  is_alert_active_any_horizon: boolean;
  temporal_consistency_valid: boolean;
  temporal_consistency_notes: string[];
  anomaly_score: number;
}

export interface EmpiricalLeadTimeMatch {
  match_id: string;
  forecast_id: string;
  forecast_timestamp: string;
  horizon_minutes: number;
  forecast_probability: number;
  decision_threshold: number;
  actual_event_id: string;
  actual_event_timestamp: string;
  actual_threat_type: string;
  empirical_lead_time_minutes: number;
  is_earliest_warning_for_event: boolean;
}

export interface LeadTimeScorecardResponse {
  evaluation_period_start?: string;
  evaluation_period_end?: string;
  status: string;
  status_message: string;
  mean_lead_time_minutes?: number;
  median_lead_time_minutes?: number;
  min_lead_time_minutes?: number;
  max_lead_time_minutes?: number;
  std_lead_time_minutes?: number;
  total_emitted_forecasts: number;
  total_attack_events: number;
  valid_forecast_event_matches: number;
  missed_attack_events: number;
  false_early_warnings: number;
  unmatched_forecasts: number;
  empirical_forecast_coverage_rate?: number;
  earliest_warning_horizon_distribution: Record<string, number>;
  matches: EmpiricalLeadTimeMatch[];
}

export interface HorizonCalibrationSummary {
  horizon_minutes: number;
  calibration_method: string;
  brier_score: number;
  expected_calibration_error: number;
  maximum_calibration_error?: number;
  log_loss?: number;
  status: string;
  conformal_target_coverage?: number;
  conformal_empirical_coverage?: number;
  conformal_average_set_size?: number;
}

export interface CalibrationMetricsResponse {
  model_version: string;
  brier_score: number;
  expected_calibration_error: number;
  reliability_diagram_bins: Array<{
    bin_midpoint: number;
    bin_range: string;
    observed_frequency: number;
    mean_confidence: number;
    sample_count: number;
    calibration_error: number;
  }>;
  evaluated_samples_count: number;
  last_calibrated_at: string;
  conformal_target_coverage: number;
  conformal_empirical_coverage?: number;
  conformal_average_set_size?: number;
  per_horizon_metrics?: Record<string, HorizonCalibrationSummary>;
}

export const forecastApi = {
  async getTimeline(targetEntity = 'GLOBAL_PERIMETER'): Promise<MultiHorizonTimelineResponse> {
    return apiClient<MultiHorizonTimelineResponse>(`/model/forecast/timeline?target_entity=${targetEntity}`);
  },

  async getLeadTimeScorecard(): Promise<LeadTimeScorecardResponse> {
    return apiClient<LeadTimeScorecardResponse>('/model/lead-time');
  },

  async getCalibrationMetrics(): Promise<CalibrationMetricsResponse> {
    return apiClient<CalibrationMetricsResponse>('/model/calibration');
  },
};
