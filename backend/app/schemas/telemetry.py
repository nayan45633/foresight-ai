"""Foresight AI - Telemetry Ingestion API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.ml.contracts import FlowRecord, TemporalWindowFeatures
from app.telemetry.job_manager import JobStatus
from app.telemetry.quality_service import TelemetryQualityReport
from app.telemetry.validation import ValidationRejection


class TelemetryIngestRequest(BaseModel):
    source_identifier: str = Field(..., description="Unique sensor / probe ID")
    flows: List[FlowRecord] = Field(..., min_length=1, max_length=5000)


class TelemetryBatchIngestRequest(BaseModel):
    source_identifier: str = Field(..., description="Unique sensor / probe ID")
    raw_records: List[Dict[str, Any]] = Field(..., min_length=1, max_length=5000)


class TelemetryIngestResponse(BaseModel):
    batch_id: str
    status: str = "ACCEPTED"
    records_received: int
    records_valid: int
    records_rejected: int = 0
    records_duplicate: int = 0
    flows_persisted: int = 0
    ingested_at: datetime
    message: str
    rejections: List[ValidationRejection] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProtocolCount(BaseModel):
    protocol: str
    count: int
    percentage: float


class TrafficTimeSeriesPoint(BaseModel):
    timestamp: datetime
    packet_count: int
    byte_count: int
    flow_count: int


class TelemetryStatsResponse(BaseModel):
    total_flows_last_hour: int
    active_sources: int
    mean_packet_rate: float
    mean_byte_rate: float
    protocol_breakdown: Dict[str, int]
    top_destination_ports: List[Dict[str, Any]] = Field(default_factory=list)
    unique_sources_count: int = 0
    unique_destinations_count: int = 0
    recent_traffic_timeline: List[TrafficTimeSeriesPoint] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PcapUploadResponse(BaseModel):
    job_id: str
    filename: str
    file_size_bytes: int
    status: JobStatus
    message: str
    status_url: str

    model_config = ConfigDict(from_attributes=True)


class PcapJobStatusResponse(BaseModel):
    job_id: str
    filename: str
    file_size_bytes: int
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    flows_generated: int = 0
    records_rejected: int = 0
    processing_duration_ms: float = 0.0
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemporalWindowsResponse(BaseModel):
    window_count: int
    window_size_seconds: int
    stride_seconds: int
    windows: List[TemporalWindowFeatures]
