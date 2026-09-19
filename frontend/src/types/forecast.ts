export type ThreatSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface FeatureContribution {
  feature_name: string;
  attribution_value: number;
  baseline_value?: number;
  observed_value?: number;
  description?: string;
}

export interface UncertaintyEstimate {
  credible_interval_lower: number;
  credible_interval_upper: number;
  confidence_level: number;
  epistemic_uncertainty: number;
  aleatoric_uncertainty: number;
}

export interface ForecastPrediction {
  threat: string;
  probability: number;
  confidence: number;
  horizon_minutes: number;
  severity: ThreatSeverity;
}

export interface ForecastResult {
  id: string;
  timestamp: string;
  forecast: ForecastPrediction;
  anomaly_score: number;
  uncertainty: UncertaintyEstimate;
  model_version: string;
  feature_contributions: FeatureContribution[];
  target_entity: string;
  is_simulated: boolean;
}

export interface MultiHorizonForecast {
  timestamp: string;
  target_entity: string;
  anomaly_score: number;
  horizons: ForecastResult[];
}
