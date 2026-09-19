/**
 * Foresight AI - Attack Path & Risk State Engine API Service
 */

import { apiClient } from './client';

export type RiskState = 'NORMAL' | 'WATCH' | 'SUSPICIOUS' | 'ELEVATED' | 'CRITICAL';

export interface AttackPathNode {
  stage: string;
  is_current: boolean;
  is_predicted: boolean;
  is_forecasted: boolean;
  probability?: number;
  evidence_strength: 'LOW' | 'MEDIUM' | 'HIGH' | 'VERIFIED' | 'INSUFFICIENT_EVIDENCE' | 'GRAPH_KNOWLEDGE_ONLY';
  status: 'OBSERVED' | 'PREDICTED' | 'GRAPH_POSSIBLE' | 'POTENTIAL_UNVALIDATED' | 'INSUFFICIENT_EVIDENCE';
  supporting_features: Array<Record<string, any>>;
  timestamp?: string;
}

export interface AttackPathEdge {
  source_stage: string;
  target_stage: string;
  transition_probability?: number;
  is_forecasted: boolean;
  transition_horizon_minutes?: number;
  evidence_reasons: string[];
  uncertainty: string;
  status: string;
}

export interface AttackPathForecast {
  forecast_id: string;
  forecast_timestamp: string;
  target_entity: string;
  current_stage?: string;
  predicted_next_stage?: string;
  subsequent_stages: string[];
  probability?: number;
  uncertainty: string;
  evidence: string[];
  supporting_features: Array<Record<string, any>>;
  horizon_minutes?: number;
  target_timestamp?: string;
  transition_confidence_status: string;
  model_version: string;
  graph_nodes: AttackPathNode[];
  graph_edges: AttackPathEdge[];
}

export interface RiskStateTransition {
  transition_id: string;
  timestamp: string;
  previous_state: RiskState;
  new_state: RiskState;
  triggering_evidence: string[];
  forecast_probability: number;
  anomaly_score: number;
  uncertainty: string;
  triggering_horizon?: number;
  reason: string;
  model_version: string;
}

export interface RiskStateEvaluation {
  evaluation_id: string;
  timestamp: string;
  current_state: RiskState;
  previous_state: RiskState;
  state_duration_seconds: number;
  cycles_in_state: number;
  is_hysteresis_dampened: boolean;
  hysteresis_notes: string[];
  max_calibrated_probability: number;
  triggering_horizon_minutes?: number;
  active_alert_horizons: number[];
  anomaly_score: number;
  conformal_coverage_status: string;
  uncertainty_level: string;
  evidence_summary: string[];
  top_risk_features: Array<Record<string, any>>;
  attack_path_summary?: AttackPathForecast;
  model_version: string;
}

export interface RiskTimelineResponse {
  current_evaluation: RiskStateEvaluation;
  timeline_transitions: RiskStateTransition[];
  historical_evaluations: RiskStateEvaluation[];
}

export const riskApi = {
  async getCurrentState(targetEntity = 'GLOBAL_PERIMETER'): Promise<RiskStateEvaluation> {
    return apiClient<RiskStateEvaluation>(`/risk/state?target_entity=${targetEntity}`);
  },

  async getTimeline(targetEntity = 'GLOBAL_PERIMETER', limit = 20): Promise<RiskTimelineResponse> {
    return apiClient<RiskTimelineResponse>(`/risk/timeline?target_entity=${targetEntity}&limit=${limit}`);
  },

  async getAttackPath(targetEntity = 'GLOBAL_PERIMETER'): Promise<AttackPathForecast> {
    return apiClient<AttackPathForecast>(`/risk/attack-path?target_entity=${targetEntity}`);
  },

  async getTransitions(limit = 20): Promise<RiskStateTransition[]> {
    return apiClient<RiskStateTransition[]>(`/risk/transitions?limit=${limit}`);
  },
};
