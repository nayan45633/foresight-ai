/**
 * Foresight AI - Telemetry & Flow Ingestion API Service
 */

import { apiClient } from './client';

export interface FlowRecord {
  id?: string;
  timestamp: string;
  source_ip: string;
  destination_ip: string;
  source_port: number;
  destination_port: number;
  protocol: string;
  flow_duration_ms: number;
  packet_count: number;
  byte_count: number;
  packet_rate?: number;
  byte_rate?: number;
  tcp_flags?: string;
  connection_state?: string;
  direction?: string;
  metadata?: Record<string, any>;
}

export interface TelemetryQualityReport {
  timestamp: string;
  total_records_received: number;
  total_records_accepted: number;
  total_records_rejected: number;
  duplicate_records_dropped: number;
  rejection_rate_percent: number;
  flows_generated_total: number;
  processing_latency_ms: number;
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  top_rejection_reasons: Record<string, number>;
  recent_sample_rejections: Record<string, string>;
}

export interface TelemetryStatsResponse {
  total_flows_last_hour: number;
  active_sources: number;
  mean_packet_rate: number;
  mean_byte_rate: number;
  protocol_breakdown: Record<string, number>;
  top_destination_ports: Array<{ port: number; count: number }>;
  unique_sources_count: number;
  unique_destinations_count: number;
  recent_traffic_timeline: Array<{
    timestamp: string;
    flow_count: number;
    packet_volume: number;
    byte_volume: number;
  }>;
}

export interface PcapUploadResponse {
  job_id: string;
  filename: string;
  file_size_bytes: number;
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  message: string;
  status_url: string;
}

export interface PcapJobStatusResponse {
  job_id: string;
  filename: string;
  file_size_bytes: number;
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  total_packets: number;
  valid_flows_extracted: number;
  error_message?: string;
  metrics?: Record<string, any>;
}

export interface TemporalWindowsResponse {
  window_count: number;
  window_size_seconds: number;
  stride_seconds: number;
  windows: Array<{
    window_id: string;
    window_start: string;
    window_end: string;
    flow_volume: number;
    packet_volume: number;
    byte_volume: number;
    packets_per_second: number;
    bytes_per_second: number;
    syn_count: number;
    unique_source_ips: number;
    unique_destination_ips: number;
    traffic_burst_score: number;
  }>;
}

export const telemetryApi = {
  async getQuality(): Promise<TelemetryQualityReport> {
    return apiClient<TelemetryQualityReport>('/telemetry/quality');
  },

  async getStatistics(): Promise<TelemetryStatsResponse> {
    return apiClient<TelemetryStatsResponse>('/telemetry/statistics');
  },

  async getRecentFlows(limit = 50, protocol?: string): Promise<FlowRecord[]> {
    const query = new URLSearchParams({ limit: limit.toString() });
    if (protocol) query.append('protocol', protocol);
    return apiClient<FlowRecord[]>(`/telemetry/recent?${query.toString()}`);
  },

  async getTemporalWindows(limitFlows = 500): Promise<TemporalWindowsResponse> {
    return apiClient<TemporalWindowsResponse>(`/telemetry/windows?limit_flows=${limitFlows}`);
  },

  async uploadPcap(file: File): Promise<PcapUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient<PcapUploadResponse>('/telemetry/pcap', {
      method: 'POST',
      body: formData,
    });
  },

  async getPcapStatus(jobId: string): Promise<PcapJobStatusResponse> {
    return apiClient<PcapJobStatusResponse>(`/telemetry/ingestion/${jobId}`);
  },
};
