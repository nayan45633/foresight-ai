"""Foresight AI - Asynchronous Telemetry Ingestion Job Manager.

Manages PCAP file uploads and large batch ingestion tasks:
- Asynchronous task processing with worker queue and concurrency limits
- State machine: QUEUED -> PROCESSING -> COMPLETED / FAILED
- Path traversal defense & safe temporary file isolation
- Automatic file cleanup upon task termination
"""

import asyncio
from datetime import datetime, timezone
import os
import shutil
import tempfile
import time
import uuid
from enum import Enum
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.core.logging import logger
from app.ml.contracts import FlowRecord
from app.telemetry.pcap_parser import PcapStreamParser
from app.telemetry.quality_service import quality_tracker


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IngestionJobRecord(BaseModel):
    job_id: str
    filename: str
    file_size_bytes: int
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    flows_generated: int = 0
    records_rejected: int = 0
    processing_duration_ms: float = 0.0
    error_message: Optional[str] = None
    target_entity: str = "GLOBAL_PERIMETER"

    model_config = ConfigDict(from_attributes=True)


class TelemetryJobManager:
    """Orchestrates asynchronous background PCAP processing jobs with backpressure limits."""

    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}
    MAX_CONCURRENT_JOBS = 4

    def __init__(self, temp_dir: Optional[str] = None):
        self._temp_dir = temp_dir or os.path.join(tempfile.gettempdir(), "foresight_pcap_staging")
        os.makedirs(self._temp_dir, exist_ok=True)
        self._jobs: Dict[str, IngestionJobRecord] = {}
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_JOBS)
        self._pcap_parser = PcapStreamParser()

    def sanitize_filename(self, filename: str) -> str:
        """Sanitizes user filename and prevents path traversal."""
        base = os.path.basename(filename)
        # Strip dangerous characters
        safe_name = "".join(c for c in base if c.isalnum() or c in (".", "-", "_"))
        return safe_name or "unnamed.pcap"

    def create_job(self, original_filename: str, file_size: int) -> IngestionJobRecord:
        """Registers a new ingestion job."""
        safe_name = self.sanitize_filename(original_filename)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension '{ext}'. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}")
        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size ({file_size} bytes) exceeds limit of {self.MAX_FILE_SIZE_BYTES} bytes")

        job_id = str(uuid.uuid4())
        record = IngestionJobRecord(
            job_id=job_id,
            filename=safe_name,
            file_size_bytes=file_size,
            status=JobStatus.QUEUED,
        )
        self._jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> Optional[IngestionJobRecord]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[IngestionJobRecord]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]

    def save_temp_pcap(self, job_id: str, content: bytes) -> str:
        """Saves uploaded binary content into isolated temporary storage."""
        safe_path = os.path.join(self._temp_dir, f"{job_id}.pcap")
        with open(safe_path, "wb") as f:
            f.write(content)
        return safe_path

    async def process_pcap_job(
        self,
        job_id: str,
        file_path: str,
        on_flows_generated: Optional[Callable[[List[FlowRecord]], None]] = None,
    ) -> None:
        """Worker task processing a PCAP file with progress updates and guaranteed cleanup."""
        job = self._jobs.get(job_id)
        if not job:
            return

        async with self._semaphore:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            start_perf = time.perf_counter()

            try:
                # Offload blocking Scapy parsing to thread pool
                loop = asyncio.get_running_loop()
                flows, stats = await loop.run_in_executor(
                    None,
                    self._pcap_parser.parse_pcap_file,
                    file_path,
                )

                duration_ms = (time.perf_counter() - start_perf) * 1000.0
                job.records_processed = stats.packets_read
                job.flows_generated = stats.flows_generated
                job.records_rejected = stats.errors
                job.processing_duration_ms = round(duration_ms, 2)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)

                # Update global telemetry quality metrics
                quality_tracker.record_batch(
                    received=stats.packets_read,
                    accepted=stats.packets_read - stats.errors - stats.packets_unsupported,
                    rejected=stats.errors,
                    duplicates=0,
                    flows_gen=stats.flows_generated,
                    latency_ms=duration_ms,
                )
                quality_tracker.record_unsupported_packets(stats.packets_unsupported)

                if on_flows_generated and flows:
                    on_flows_generated(flows)

                logger.info(
                    f"Job {job_id} completed: {stats.packets_read} pkts -> {stats.flows_generated} flows in {duration_ms:.2f}ms"
                )

            except Exception as e:
                duration_ms = (time.perf_counter() - start_perf) * 1000.0
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                job.processing_duration_ms = round(duration_ms, 2)
                logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

            finally:
                # Guaranteed cleanup of temporary upload file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as clean_err:
                    logger.warning(f"Could not remove temporary file {file_path}: {clean_err}")


# Global job manager singleton
job_manager = TelemetryJobManager()
