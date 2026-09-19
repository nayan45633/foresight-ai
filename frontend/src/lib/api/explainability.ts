/**
 * Foresight AI - SHAP Explainability API Service
 */

import { apiClient } from './client';
import { FeatureAttributionDetail } from './forecast';

export interface GlobalFeatureImportanceItem {
  feature_name: string;
  feature_index: number;
  mean_abs_shap: number;
  unit?: string;
  description: string;
  rank: number;
}

export interface HorizonMatrixRow {
  feature_name: string;
  feature_index: number;
  unit?: string;
  description: string;
  overall_mean_abs_shap: number;
  shap_5m: number;
  shap_15m: number;
  shap_30m: number;
  shap_60m: number;
}

export interface GlobalExplainResponse {
  model_version: string;
  schema_version: string;
  evaluated_samples_count: number;
  generated_at: string;
  top_global_features: GlobalFeatureImportanceItem[];
  horizon_comparison_matrix: HorizonMatrixRow[];
}

export interface InstanceExplainResponse {
  horizon_minutes: number;
  status: string;
  model_version: string;
  schema_version: string;
  calibrated_probability: number;
  raw_probability?: number;
  raw_margin: number;
  base_value: number;
  top_positive_contributors: FeatureAttributionDetail[];
  top_negative_contributors: FeatureAttributionDetail[];
  additivity_verified: boolean;
  additivity_delta?: number;
  computation_latency_ms: number;
}

export const explainabilityApi = {
  async getGlobal(): Promise<GlobalExplainResponse> {
    return apiClient<GlobalExplainResponse>('/model/explain/global');
  },

  async explainHorizon(horizonMinutes: number, topK = 6): Promise<InstanceExplainResponse> {
    return apiClient<InstanceExplainResponse>('/model/explain', {
      method: 'POST',
      body: JSON.stringify({
        horizon_minutes: horizonMinutes,
        top_k: topK,
      }),
    });
  },
};
