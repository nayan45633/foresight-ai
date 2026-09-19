"""Foresight AI - Network Telemetry Ingestion & Stream Endpoints."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models.telemetry import NetworkFlow, TelemetryBatch
from app.db.models.telemetry_job import TelemetryJob
from app.db.session import AsyncSessionLocal, get_db
from app.ml.contracts import FlowRecord, TemporalWindowFeatures
from app.schemas.telemetry import (
    PcapJobStatusResponse,
    PcapUploadResponse,
    TelemetryBatchIngestRequest,
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    TelemetryStatsResponse,
    TemporalWindowsResponse,
    TrafficTimeSeriesPoint,
)
from app.telemetry.deduplication import TelemetryDeduplicator
from app.telemetry.job_manager import JobStatus, job_manager
from app.telemetry.quality_service import TelemetryQualityReport, quality_tracker
from app.telemetry.validation import TelemetryValidator
from app.telemetry.window_generator import SlidingWindowGenerator

router = APIRouter()
deduplicator = TelemetryDeduplicator()


async def _save_flows_to_db(flows: List[FlowRecord], source_id: str, job_id: Optional[str] = None) -> None:
    """Helper saving flows asynchronously to database and updating job state."""
    if not flows:
        return
    async with AsyncSessionLocal() as db:
        try:
            batch = TelemetryBatch(
                id=str(uuid.uuid4()),
                source_identifier=source_id,
                record_count=len(flows),
                ingested_at=datetime.now(timezone.utc),
                status="SUCCESS",
            )
            db.add(batch)

            for flow in flows:
                flow_id = flow.id if (flow.id and len(flow.id) <= 36) else str(uuid.uuid4())
                db_flow = NetworkFlow(
                    id=flow_id,
                    timestamp=flow.timestamp,
                    source_ip=flow.source_ip,
                    destination_ip=flow.destination_ip,
                    source_port=flow.source_port,
                    destination_port=flow.destination_port,
                    protocol=flow.protocol.value,
                    flow_duration_ms=flow.flow_duration_ms,
                    packet_count=flow.packet_count,
                    byte_count=flow.byte_count,
                    packet_rate=flow.packet_rate or 0.0,
                    byte_rate=flow.byte_rate or 0.0,
                    tcp_flags=flow.tcp_flags or "",
                    connection_state=flow.connection_state or "UNKNOWN",
                    direction=flow.direction.value,
                    metadata_payload=flow.metadata or {},
                )
                db.add(db_flow)
            
            if job_id:
                job_rec = await db.get(TelemetryJob, job_id)
                if job_rec:
                    job_rec.status = "COMPLETED"
                    job_rec.valid_flow_count = len(flows)
                    job_rec.record_count = len(flows)
                    job_rec.completed_at = datetime.now(timezone.utc)
                    job_rec.quality_summary = {"flows_persisted": len(flows)}
            
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to persist flows to database: {e}", exc_info=True)


@router.post("/flows", response_model=TelemetryIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_flows(
    payload: TelemetryIngestRequest,
    db: AsyncSession = Depends(get_db)
) -> TelemetryIngestResponse:
    """Ingests a normalized batch of network flow telemetry with deduplication."""
    start_time = time.perf_counter()
    if len(payload.flows) > settings.MAX_BATCH_FLOW_RECORDS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum limit of {settings.MAX_BATCH_FLOW_RECORDS} flows",
        )

    batch_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Apply Deduplication
    unique_flows, duplicate_count = deduplicator.filter_duplicates(payload.flows)

    # Persist Batch Record
    batch = TelemetryBatch(
        id=batch_id,
        source_identifier=payload.source_identifier,
        record_count=len(payload.flows),
        ingested_at=now,
        status="SUCCESS",
    )
    db.add(batch)

    # Persist Individual Flows
    for flow in unique_flows:
        db_flow = NetworkFlow(
            id=flow.id or str(uuid.uuid4()),
            timestamp=flow.timestamp,
            source_ip=flow.source_ip,
            destination_ip=flow.destination_ip,
            source_port=flow.source_port,
            destination_port=flow.destination_port,
            protocol=flow.protocol.value,
            flow_duration_ms=flow.flow_duration_ms,
            packet_count=flow.packet_count,
            byte_count=flow.byte_count,
            packet_rate=flow.packet_rate or 0.0,
            byte_rate=flow.byte_rate or 0.0,
            tcp_flags=flow.tcp_flags or "",
            connection_state=flow.connection_state or "UNKNOWN",
            direction=flow.direction.value,
            metadata_payload=flow.metadata,
        )
        db.add(db_flow)

    await db.flush()
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Track Data Quality
    quality_tracker.record_batch(
        received=len(payload.flows),
        accepted=len(unique_flows),
        rejected=0,
        duplicates=duplicate_count,
        flows_gen=len(unique_flows),
        latency_ms=latency_ms,
    )

    return TelemetryIngestResponse(
        batch_id=batch_id,
        status="ACCEPTED",
        records_received=len(payload.flows),
        records_valid=len(payload.flows),
        records_duplicate=duplicate_count,
        flows_persisted=len(unique_flows),
        ingested_at=now,
        message=f"Ingested {len(unique_flows)} unique flows ({duplicate_count} duplicates skipped) from {payload.source_identifier}",
        rejections=[],
    )


@router.post("/flows/batch", response_model=TelemetryIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_raw_batch(
    payload: TelemetryBatchIngestRequest,
    db: AsyncSession = Depends(get_db)
) -> TelemetryIngestResponse:
    """Validates, sanitizes, and ingests a raw heterogeneous JSON telemetry stream."""
    start_time = time.perf_counter()
    if len(payload.raw_records) > settings.MAX_BATCH_FLOW_RECORDS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum limit of {settings.MAX_BATCH_FLOW_RECORDS} records",
        )

    batch_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 1. Validate & Sanitize Batch
    report = TelemetryValidator.validate_batch(payload.raw_records)

    # 2. Filter Duplicates
    unique_flows, duplicate_count = deduplicator.filter_duplicates(report.valid_flows)

    # 3. Persist Batch Record
    batch = TelemetryBatch(
        id=batch_id,
        source_identifier=payload.source_identifier,
        record_count=len(payload.raw_records),
        ingested_at=now,
        status="SUCCESS" if report.valid_count > 0 else "FAILED",
        error_summary=f"{report.rejected_count} rejected" if report.rejected_count > 0 else None,
    )
    db.add(batch)

    # 4. Persist Valid Unique Flows
    for flow in unique_flows:
        db_flow = NetworkFlow(
            id=flow.id or str(uuid.uuid4()),
            timestamp=flow.timestamp,
            source_ip=flow.source_ip,
            destination_ip=flow.destination_ip,
            source_port=flow.source_port,
            destination_port=flow.destination_port,
            protocol=flow.protocol.value,
            flow_duration_ms=flow.flow_duration_ms,
            packet_count=flow.packet_count,
            byte_count=flow.byte_count,
            packet_rate=flow.packet_rate or 0.0,
            byte_rate=flow.byte_rate or 0.0,
            tcp_flags=flow.tcp_flags or "",
            connection_state=flow.connection_state or "UNKNOWN",
            direction=flow.direction.value,
            metadata_payload=flow.metadata,
        )
        db.add(db_flow)

    await db.flush()
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Aggregate rejection reasons
    rejection_reasons_map: Dict[str, int] = {}
    samples_map: Dict[str, str] = {}
    for r in report.rejections:
        rejection_reasons_map[r.reason_code] = rejection_reasons_map.get(r.reason_code, 0) + 1
        if r.reason_code not in samples_map:
            samples_map[r.reason_code] = r.message

    # Record Quality Metrics
    quality_tracker.record_batch(
        received=report.total_received,
        accepted=len(unique_flows),
        rejected=report.rejected_count,
        duplicates=duplicate_count,
        flows_gen=len(unique_flows),
        latency_ms=latency_ms,
        rejection_reasons=rejection_reasons_map,
        samples=samples_map,
    )

    return TelemetryIngestResponse(
        batch_id=batch_id,
        status="ACCEPTED" if report.valid_count > 0 else "REJECTED",
        records_received=report.total_received,
        records_valid=report.valid_count,
        records_rejected=report.rejected_count,
        records_duplicate=duplicate_count,
        flows_persisted=len(unique_flows),
        ingested_at=now,
        message=f"Validated {report.total_received} records: {len(unique_flows)} unique persisted, {report.rejected_count} rejected, {duplicate_count} duplicates",
        rejections=report.rejections[:50],  # Return up to 50 sample rejections
    )


@router.post("/pcap", response_model=PcapUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_pcap_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> PcapUploadResponse:
    """Uploads a PCAP/PCAPNG file for asynchronous parsing and flow reconstruction."""
    filename = file.filename or "telemetry.pcap"
    
    # Read file content safely
    content = await file.read()
    file_size = len(content)

    try:
        job = job_manager.create_job(filename, file_size)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    # Persist job record in database
    db_job = TelemetryJob(
        id=job.job_id,
        source_type="PCAP",
        file_name=job.filename,
        file_size_bytes=job.file_size_bytes,
        status="PROCESSING",
        started_at=datetime.now(timezone.utc),
        quality_summary={},
    )
    db.add(db_job)
    await db.flush()

    # Save to safe temporary file
    temp_path = job_manager.save_temp_pcap(job.job_id, content)

    # Callback to save flows to db when parsing completes
    def persist_flows_callback(flows: List[FlowRecord]):
        asyncio.create_task(_save_flows_to_db(flows, source_id=f"pcap:{job.filename}", job_id=job.job_id))

    # Spawn background task
    background_tasks.add_task(
        job_manager.process_pcap_job,
        job.job_id,
        temp_path,
        persist_flows_callback,
    )

    return PcapUploadResponse(
        job_id=job.job_id,
        filename=job.filename,
        file_size_bytes=job.file_size_bytes,
        status=job.status,
        message="PCAP file accepted and queued for background flow reconstruction",
        status_url=f"{settings.API_V1_STR}/telemetry/ingestion/{job.job_id}",
    )


@router.get("/ingestion/{job_id}", response_model=PcapJobStatusResponse)
async def get_ingestion_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> PcapJobStatusResponse:
    """Checks the status and metrics of an asynchronous PCAP ingestion task."""
    job = job_manager.get_job(job_id)
    if job:
        return PcapJobStatusResponse(**job.model_dump())
        
    # Check DB fallback
    db_job = await db.get(TelemetryJob, job_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found",
        )
    return PcapJobStatusResponse(
        job_id=db_job.id,
        filename=db_job.file_name or "unknown",
        file_size_bytes=db_job.file_size_bytes,
        status=JobStatus(db_job.status),
        created_at=db_job.created_at,
        started_at=db_job.started_at,
        completed_at=db_job.completed_at,
        total_packets=db_job.record_count,
        valid_flows_extracted=db_job.valid_flow_count,
        error_message=db_job.error_state,
        metrics=db_job.quality_summary,
    )


@router.get("/quality", response_model=TelemetryQualityReport)
async def get_telemetry_quality() -> TelemetryQualityReport:
    """Retrieves real-time data quality, validation health, and rejection metrics."""
    return quality_tracker.get_report()


@router.get("/recent", response_model=List[FlowRecord])
async def get_recent_flows(
    limit: int = Query(default=50, ge=1, le=500),
    protocol: Optional[str] = None,
    source_ip: Optional[str] = None,
    destination_ip: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves recent network flows with optional protocol and IP filtering."""
    stmt = select(NetworkFlow).order_by(NetworkFlow.timestamp.desc())
    if protocol:
        stmt = stmt.where(NetworkFlow.protocol == protocol.upper())
    if source_ip:
        stmt = stmt.where(NetworkFlow.source_ip == source_ip)
    if destination_ip:
        stmt = stmt.where(NetworkFlow.destination_ip == destination_ip)
        
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    flows = result.scalars().all()
    
    return [
        FlowRecord(
            id=f.id,
            timestamp=f.timestamp,
            source_ip=f.source_ip,
            destination_ip=f.destination_ip,
            source_port=f.source_port,
            destination_port=f.destination_port,
            protocol=f.protocol,
            flow_duration_ms=f.flow_duration_ms,
            packet_count=f.packet_count,
            byte_count=f.byte_count,
            packet_rate=f.packet_rate,
            byte_rate=f.byte_rate,
            tcp_flags=f.tcp_flags,
            connection_state=f.connection_state,
            direction=f.direction,
            metadata=f.metadata_payload,
        )
        for f in flows
    ]


@router.get("/statistics", response_model=TelemetryStatsResponse)
async def get_telemetry_statistics(db: AsyncSession = Depends(get_db)) -> TelemetryStatsResponse:
    """Calculates real-time aggregation statistics over recent telemetry."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    # Query count in last hour
    count_result = await db.execute(
        select(func.count(NetworkFlow.id)).where(NetworkFlow.timestamp >= one_hour_ago)
    )
    total_flows = count_result.scalar_one() or 0
    
    # Query active sources
    sources_result = await db.execute(
        select(func.count(func.distinct(TelemetryBatch.source_identifier)))
    )
    active_sources = sources_result.scalar_one() or 0
    
    # Query unique IPs
    uniq_src_res = await db.execute(
        select(func.count(func.distinct(NetworkFlow.source_ip))).where(NetworkFlow.timestamp >= one_hour_ago)
    )
    uniq_sources = uniq_src_res.scalar_one() or 0

    uniq_dst_res = await db.execute(
        select(func.count(func.distinct(NetworkFlow.destination_ip))).where(NetworkFlow.timestamp >= one_hour_ago)
    )
    uniq_destinations = uniq_dst_res.scalar_one() or 0

    # Query averages
    avg_result = await db.execute(
        select(
            func.avg(NetworkFlow.packet_rate),
            func.avg(NetworkFlow.byte_rate),
        ).where(NetworkFlow.timestamp >= one_hour_ago)
    )
    avg_pkt, avg_byte = avg_result.first() or (0.0, 0.0)

    # Query protocol breakdown
    proto_result = await db.execute(
        select(NetworkFlow.protocol, func.count(NetworkFlow.id))
        .where(NetworkFlow.timestamp >= one_hour_ago)
        .group_by(NetworkFlow.protocol)
    )
    proto_breakdown = {proto: count for proto, count in proto_result.all()}

    # Top destination ports
    top_ports_res = await db.execute(
        select(NetworkFlow.destination_port, func.count(NetworkFlow.id).label("cnt"))
        .where(NetworkFlow.timestamp >= one_hour_ago)
        .group_by(NetworkFlow.destination_port)
        .order_by(desc("cnt"))
        .limit(5)
    )
    top_ports = [{"port": p, "count": c} for p, c in top_ports_res.all()]

    return TelemetryStatsResponse(
        total_flows_last_hour=total_flows,
        active_sources=active_sources,
        mean_packet_rate=float(avg_pkt or 0.0),
        mean_byte_rate=float(avg_byte or 0.0),
        protocol_breakdown=proto_breakdown,
        top_destination_ports=top_ports,
        unique_sources_count=uniq_sources,
        unique_destinations_count=uniq_destinations,
        recent_traffic_timeline=[],
    )


@router.get("/windows", response_model=TemporalWindowsResponse)
async def get_temporal_windows(
    window_size_seconds: int = Query(default=60, ge=10, le=3600),
    stride_seconds: int = Query(default=30, ge=5, le=1800),
    limit_flows: int = Query(default=500, ge=10, le=5000),
    db: AsyncSession = Depends(get_db)
) -> TemporalWindowsResponse:
    """Slices recent flows into sliding temporal windows with extracted behavioral features."""
    result = await db.execute(
        select(NetworkFlow).order_by(NetworkFlow.timestamp.desc()).limit(limit_flows)
    )
    db_flows = result.scalars().all()
    
    flow_records = [
        FlowRecord(
            id=f.id,
            timestamp=f.timestamp,
            source_ip=f.source_ip,
            destination_ip=f.destination_ip,
            source_port=f.source_port,
            destination_port=f.destination_port,
            protocol=f.protocol,
            flow_duration_ms=f.flow_duration_ms,
            packet_count=f.packet_count,
            byte_count=f.byte_count,
            packet_rate=f.packet_rate,
            byte_rate=f.byte_rate,
            tcp_flags=f.tcp_flags,
            connection_state=f.connection_state,
            direction=f.direction,
            metadata=f.metadata_payload,
        )
        for f in reversed(db_flows)  # Reverse to chronological order
    ]

    generator = SlidingWindowGenerator(
        window_size_seconds=window_size_seconds,
        stride_seconds=stride_seconds,
    )
    windows = generator.generate_windows_from_flows(flow_records)

    return TemporalWindowsResponse(
        window_count=len(windows),
        window_size_seconds=window_size_seconds,
        stride_seconds=stride_seconds,
        windows=windows,
    )
