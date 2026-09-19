"""Foresight AI - Telemetry Data Quality & Integrity Engine."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RejectionSummary(BaseModel):
    reason_code: str
    count: int
    sample_message: Optional[str] = None


class TelemetryQualityReport(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records_ingested: int = 0
    accepted_records_count: int = 0
    rejected_records_count: int = 0
    duplicate_records_count: int = 0
    invalid_records_count: int = 0
    unsupported_packets_count: int = 0
    flows_generated_count: int = 0
    acceptance_rate_percentage: float = 100.0
    mean_processing_latency_ms: float = 0.0
    rejection_reasons: List[RejectionSummary] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TelemetryQualityTracker:
    """Thread-safe telemetry data quality metrics accumulator."""

    def __init__(self):
        self.total_records = 0
        self.accepted_records = 0
        self.rejected_records = 0
        self.duplicate_records = 0
        self.invalid_records = 0
        self.unsupported_packets = 0
        self.flows_generated = 0
        self.total_latency_ms = 0.0
        self.batch_count = 0
        self.rejection_counts: Dict[str, int] = {}
        self.rejection_samples: Dict[str, str] = {}

    def record_batch(
        self,
        received: int,
        accepted: int,
        rejected: int,
        duplicates: int,
        flows_gen: int,
        latency_ms: float,
        rejection_reasons: Optional[Dict[str, int]] = None,
        samples: Optional[Dict[str, str]] = None,
    ) -> None:
        self.total_records += received
        self.accepted_records += accepted
        self.rejected_records += rejected
        self.duplicate_records += duplicates
        self.flows_generated += flows_gen
        self.total_latency_ms += latency_ms
        self.batch_count += 1

        if rejection_reasons:
            for code, count in rejection_reasons.items():
                self.rejection_counts[code] = self.rejection_counts.get(code, 0) + count
        if samples:
            for code, sample in samples.items():
                self.rejection_samples[code] = sample

    def record_unsupported_packets(self, count: int) -> None:
        self.unsupported_packets += count

    def get_report(self) -> TelemetryQualityReport:
        rate = (
            (float(self.accepted_records) / float(self.total_records) * 100.0)
            if self.total_records > 0
            else 100.0
        )
        mean_lat = (
            (self.total_latency_ms / float(self.batch_count))
            if self.batch_count > 0
            else 0.0
        )

        rejection_summaries = [
            RejectionSummary(
                reason_code=code,
                count=count,
                sample_message=self.rejection_samples.get(code),
            )
            for code, count in sorted(self.rejection_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return TelemetryQualityReport(
            timestamp=datetime.now(timezone.utc),
            total_records_ingested=self.total_records,
            accepted_records_count=self.accepted_records,
            rejected_records_count=self.rejected_records,
            duplicate_records_count=self.duplicate_records,
            invalid_records_count=self.rejected_records,
            unsupported_packets_count=self.unsupported_packets,
            flows_generated_count=self.flows_generated,
            acceptance_rate_percentage=round(rate, 2),
            mean_processing_latency_ms=round(mean_lat, 2),
            rejection_reasons=rejection_summaries,
        )


# Global singleton instance for runtime tracking
quality_tracker = TelemetryQualityTracker()
