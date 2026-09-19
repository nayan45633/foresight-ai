export type Protocol = 'TCP' | 'UDP' | 'ICMP' | 'GRE' | 'OTHER';
export type FlowDirection = 'ingress' | 'egress' | 'internal';

export interface FlowRecord {
  id?: string;
  timestamp: string;
  end_timestamp?: string;
  source_ip: string;
  destination_ip: string;
  source_port: number;
  destination_port: number;
  protocol: Protocol;
  flow_duration_ms: number;
  packet_count: number;
  byte_count: number;
  packet_rate?: number;
  byte_rate?: number;
  forward_packets?: number;
  backward_packets?: number;
  forward_bytes?: number;
  backward_bytes?: number;
  tcp_flags?: string;
  connection_state?: string;
  direction: FlowDirection;
  metadata?: Record<string, any>;
}

export interface TelemetryStats {
  total_flows_last_hour: number;
  active_sources: number;
  mean_packet_rate: number;
  mean_byte_rate: number;
  protocol_breakdown: Record<string, number>;
  top_destination_ports: Array<{ port: number; count: number }>;
  unique_sources_count: number;
  unique_destinations_count: number;
}

export interface RejectionSummary {
  reason_code: string;
  count: number;
  sample_message?: string;
}

export interface TelemetryQualityReport {
  timestamp: string;
  total_records_ingested: number;
  accepted_records_count: number;
  rejected_records_count: number;
  duplicate_records_count: number;
  invalid_records_count: number;
  unsupported_packets_count: number;
  flows_generated_count: number;
  acceptance_rate_percentage: number;
  mean_processing_latency_ms: number;
  rejection_reasons: RejectionSummary[];
}

export type JobStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface PcapJobStatus {
  job_id: string;
  filename: string;
  file_size_bytes: number;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  records_processed: number;
  flows_generated: number;
  records_rejected: number;
  processing_duration_ms: number;
  error_message?: string;
}

export interface PcapUploadResponse {
  job_id: string;
  filename: string;
  file_size_bytes: number;
  status: JobStatus;
  message: string;
  status_url: string;
}
