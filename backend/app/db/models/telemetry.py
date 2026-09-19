"""Foresight AI - Network Telemetry & Flow Ingestion ORM Models."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class NetworkFlow(Base, TimestampMixin):
    """Normalized network flow record ingested from network sensors / probes."""
    __tablename__ = "network_flows"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False
    )
    source_ip: Mapped[str] = mapped_column(String(45), index=True, nullable=False)
    destination_ip: Mapped[str] = mapped_column(String(45), index=True, nullable=False)
    source_port: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_port: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # TCP, UDP, ICMP
    
    # Quantitative Flow Statistics
    flow_duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    packet_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    byte_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    packet_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    byte_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # TCP Flags & Protocol State
    tcp_flags: Mapped[str] = mapped_column(String(32), default="", nullable=False)  # SYN, ACK, FIN, RST, etc.
    connection_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="ingress", nullable=False)
    
    # Extensibility payload for probe-specific telemetry
    metadata_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("idx_flows_time_src_dst", "timestamp", "source_ip", "destination_ip"),
        Index("idx_flows_dst_port_proto", "destination_port", "protocol"),
    )


class TelemetryBatch(Base, TimestampMixin):
    """Tracks batch ingestion runs for integrity, lag monitoring and replay capabilities."""
    __tablename__ = "telemetry_batches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    source_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False)
    error_summary: Mapped[str] = mapped_column(String(500), nullable=True)


class TelemetrySource(Base, TimestampMixin):
    """Registers external network taps, Zeek/Suricata probes, NetFlow collectors, and PCAP drops."""
    __tablename__ = "telemetry_sources"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # PCAP_DROP, ZEEX_LOG, NETFLOW_V9, IPFIX, SFLOW
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

