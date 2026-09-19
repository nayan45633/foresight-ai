/**
 * Foresight AI - Counterfactual What-If Simulation API Service
 */

import { apiClient } from './client';

export interface AppliedFeaturePerturbation {
  feature_name: string;
  feature_index: number;
  original_value: number;
  perturbed_value: number;
  mode: string;
  delta: number;
  delta_percent?: number;
  classification: string;
  unit?: string;
  is_derived_auto_sync: boolean;
}

export interface ShapDeltaItem {
  feature_name: string;
  feature_index: number;
  baseline_shap: number;
  counterfactual_shap: number;
  delta_shap: number;
  direction: string;
  baseline_observed: number;
  counterfactual_observed: number;
  unit?: string;
}

export interface HorizonCounterfactualResult {
  horizon_minutes: number;
  baseline_probability: number;
  counterfactual_probability: number;
  probability_delta: number;
  baseline_alert: boolean;
  counterfactual_alert: boolean;
  decision_flip: string;
  decision_threshold: number;
  baseline_conformal_set: number[];
  counterfactual_conformal_set: number[];
  conformal_set_transition: string;
  baseline_uncertainty_score: number;
  counterfactual_uncertainty_score: number;
  baseline_uncertainty_level: string;
  counterfactual_uncertainty_level: string;
  shap_deltas: ShapDeltaItem[];
  top_increased_risk_features: string[];
  top_decreased_risk_features: string[];
}

export interface CounterfactualScenarioRequest {
  scenario_name?: string;
  description?: string;
  baseline_features?: Record<string, number>;
  perturbations: Record<string, number>;
  recompute_derived?: boolean;
  horizons?: number[];
  include_shap?: boolean;
}

export interface CounterfactualScenarioResponse {
  scenario_id: string;
  scenario_name: string;
  description?: string;
  timestamp: string;
  scientific_disclaimer: string;
  model_version: string;
  applied_perturbations: AppliedFeaturePerturbation[];
  horizon_results: Record<string, HorizonCounterfactualResult>;
  any_decision_flipped: boolean;
  max_risk_reduction: number;
  max_risk_elevation: number;
  execution_latency_ms: number;
  baseline_vector_summary: Record<string, number>;
  counterfactual_vector_summary: Record<string, number>;
}

export interface CounterfactualPreset {
  preset_id: string;
  title: string;
  category: string;
  description: string;
  perturbations: Record<string, number>;
  recompute_derived: boolean;
  suggested_use_case: string;
}

export interface FeatureMetadataItem {
  index: number;
  name: string;
  display_name: string;
  datatype: string;
  unit?: string;
  category: string;
  classification: string;
  min_value: number;
  max_value: number;
  default_value: number;
  slider_step: number;
  description: string;
  positive_risk_meaning: string;
  negative_risk_meaning: string;
}

export interface FeatureMetadataCatalogResponse {
  schema_version: string;
  total_features: number;
  features: FeatureMetadataItem[];
  presets: CounterfactualPreset[];
  scientific_disclaimer: string;
}

export const counterfactualApi = {
  async getCatalog(): Promise<FeatureMetadataCatalogResponse> {
    return apiClient<FeatureMetadataCatalogResponse>('/model/counterfactual/features');
  },

  async getPresets(): Promise<CounterfactualPreset[]> {
    return apiClient<CounterfactualPreset[]>('/model/counterfactual/presets');
  },

  async evaluateScenario(payload: CounterfactualScenarioRequest): Promise<CounterfactualScenarioResponse> {
    return apiClient<CounterfactualScenarioResponse>('/model/counterfactual', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getRecentScenarios(limit = 20): Promise<CounterfactualScenarioResponse[]> {
    return apiClient<CounterfactualScenarioResponse[]>(`/model/counterfactual/scenarios?limit=${limit}`);
  },

  async getScenarioById(scenarioId: string): Promise<CounterfactualScenarioResponse> {
    return apiClient<CounterfactualScenarioResponse>(`/model/counterfactual/scenario/${scenarioId}`);
  },
};
