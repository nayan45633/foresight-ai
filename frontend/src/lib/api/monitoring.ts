/**
 * Foresight AI - Model Monitoring & Observability API Service (Step 11)
 */

import { apiClient } from './client';

export interface HealthSignal {
  category: string;
  status: 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'CRITICAL';
  details: string;
  is_blocking: boolean;
}

export interface CompositeModelHealthReport {
  evaluation_timestamp: string;
  model_version: string;
  feature_schema_version: string;
  calibration_version: string;
  conformal_version: string;
  overall_status: 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'CRITICAL';
  artifact_integrity_verified: boolean;
  artifact_checksums_match: boolean;
  inference_p50_latency_ms: number;
  inference_p95_latency_ms: number;
  recent_error_rate: number;
  signals: HealthSignal[];
  summary_message: string;
}

export interface FeatureQualityMetric {
  feature_name: string;
  feature_index: number;
  missing_count: number;
  missing_rate: number;
  nan_count: number;
  inf_count: number;
  min_observed: number;
  max_observed: number;
  mean_observed: number;
  std_observed: number;
  range_violations: number;
  status: 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'CRITICAL';
}

export interface DataQualityReport {
  evaluation_timestamp: string;
  sample_count: number;
  total_features_monitored: number;
  schema_version: string;
  overall_status: 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'CRITICAL';
  completeness_score: number;
  validity_score: number;
  duplicate_rate: number;
  feature_metrics: FeatureQualityMetric[];
  anomalies_detected: string[];
  summary_message: string;
}

export interface FeatureDriftMetric {
  feature_name: string;
  feature_index: number;
  psi_score: number | null;
  ks_statistic: number | null;
  baseline_mean: number;
  current_mean: number;
  baseline_std: number;
  current_std: number;
  status: 'INSUFFICIENT_DATA' | 'STABLE' | 'MODERATE_DRIFT' | 'SIGNIFICANT_DRIFT';
  interpretation: string;
}

export interface PredictionDriftSummary {
  sample_count: number;
  positive_rate_baseline: number;
  positive_rate_current: number;
  rate_shift_delta: number;
  mean_predicted_probability: number;
  percentiles: Record<string, number>;
  status: 'INSUFFICIENT_DATA' | 'STABLE' | 'MODERATE_DRIFT' | 'SIGNIFICANT_DRIFT';
  interpretation: string;
}

export interface DriftReport {
  evaluation_timestamp: string;
  baseline_sample_count: number;
  current_sample_count: number;
  min_required_samples: number;
  overall_drift_status: 'INSUFFICIENT_DATA' | 'STABLE' | 'MODERATE_DRIFT' | 'SIGNIFICANT_DRIFT';
  drifted_features_count: number;
  total_features_monitored: number;
  feature_drift_metrics: FeatureDriftMetric[];
  prediction_drift: Record<string, PredictionDriftSummary>;
  summary_message: string;
}

export interface HorizonCalibrationHealth {
  horizon_minutes: number;
  sample_count: number;
  status: 'AWAITING_GROUND_TRUTH' | 'CALIBRATED' | 'WATCH' | 'DEGRADED';
  brier_score: number | null;
  expected_calibration_error: number | null;
  maximum_calibration_error: number | null;
  conformal_target_coverage: number;
  conformal_empirical_coverage: number | null;
  conformal_coverage_gap: number | null;
  reliability_bins: Array<{
    bin_index: number;
    bin_lower: number;
    bin_upper: number;
    sample_count: number;
    mean_confidence: number;
    observed_frequency: number;
    calibration_error: number;
  }>;
  interpretation: string;
}

export interface CalibrationHealthReport {
  evaluation_timestamp: string;
  model_version: string;
  overall_status: 'AWAITING_GROUND_TRUTH' | 'CALIBRATED' | 'WATCH' | 'DEGRADED';
  has_ground_truth: boolean;
  samples_evaluated: number;
  per_horizon_calibration: Record<string, HorizonCalibrationHealth>;
  summary_message: string;
}

export interface HorizonPerformanceMetric {
  horizon_minutes: number;
  sample_count: number;
  attack_events_count: number;
  status: 'INSUFFICIENT_EMPIRICAL_EVIDENCE' | 'OPTIMAL' | 'ACCEPTABLE' | 'DEGRADED';
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  mean_empirical_lead_time_minutes: number | null;
  interpretation: string;
}

export interface ForecastPerformanceReport {
  evaluation_timestamp: string;
  model_version: string;
  overall_status: 'INSUFFICIENT_EMPIRICAL_EVIDENCE' | 'OPTIMAL' | 'ACCEPTABLE' | 'DEGRADED';
  has_sufficient_events: boolean;
  total_evaluated_samples: number;
  total_confirmed_attacks: number;
  per_horizon_performance: Record<string, HorizonPerformanceMetric>;
  summary_message: string;
}

export const monitoringApi = {
  async getModelHealth(): Promise<CompositeModelHealthReport> {
    return apiClient<CompositeModelHealthReport>('/monitoring/health');
  },

  async getDataQuality(): Promise<DataQualityReport> {
    return apiClient<DataQualityReport>('/monitoring/data-quality');
  },

  async getDriftReport(): Promise<DriftReport> {
    return apiClient<DriftReport>('/monitoring/drift');
  },

  async getCalibrationReport(): Promise<CalibrationHealthReport> {
    return apiClient<CalibrationHealthReport>('/monitoring/calibration');
  },

  async getPerformanceReport(): Promise<ForecastPerformanceReport> {
    return apiClient<ForecastPerformanceReport>('/monitoring/performance');
  },
};
