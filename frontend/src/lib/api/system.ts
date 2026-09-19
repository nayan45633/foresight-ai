/**
 * Foresight AI - System Health, Model Registry & Audit Logs API Service
 */

import { apiClient } from './client';

export interface HealthCheckResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
  python_version: string;
  system: string;
}

export interface ReadinessResponse {
  status: string;
  database: string;
  active_model_version: string;
  timestamp: string;
}

export interface ModelVersionRecord {
  id: string;
  version_tag: string;
  model_architecture: string;
  status: 'ACTIVE' | 'CANDIDATE' | 'RETIRED' | 'ARCHIVED';
  feature_schema_version: string;
  calibration_version: string;
  conformal_version: string;
  brier_score?: number;
  expected_calibration_error?: number;
  f1_score?: number;
  precision_score?: number;
  recall_score?: number;
  roc_auc_score?: number;
  conformal_target_coverage: number;
  conformal_empirical_coverage?: number;
  hyperparameters: Record<string, any>;
  metrics_summary: Record<string, any>;
  artifact_path?: string;
  description?: string;
  trained_at?: string;
  activated_at?: string;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  actor: string;
  actor_user_id?: string;
  action: string;
  resource: string;
  resource_id?: string;
  client_ip?: string;
  status: string;
  details: Record<string, any>;
  created_at: string;
}

export const systemApi = {
  async getHealth(): Promise<HealthCheckResponse> {
    return apiClient<HealthCheckResponse>('/health');
  },

  async getReadiness(): Promise<ReadinessResponse> {
    return apiClient<ReadinessResponse>('/ready');
  },

  async getModelVersions(): Promise<ModelVersionRecord[]> {
    return apiClient<ModelVersionRecord[]>('/model/versions');
  },

  async getCurrentModelVersion(): Promise<ModelVersionRecord> {
    return apiClient<ModelVersionRecord>('/model/current');
  },

  async getAuditLogs(skip = 0, limit = 50, action?: string): Promise<AuditLogItem[]> {
    const query = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() });
    if (action) query.append('action', action);
    return apiClient<AuditLogItem[]>(`/audit/logs?${query.toString()}`);
  },
};
