"""Foresight AI - Strict Network Telemetry Validation Engine.

Validates IPv4/IPv6 addresses, transport ports, timestamps, counter bounds,
and sanitizes input without terminating full batch ingestion runs on isolated malformed records.
"""

from datetime import datetime, timezone
import ipaddress
import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.ml.contracts import FlowDirectionEnum, FlowRecord, ProtocolEnum


class ValidationRejection(BaseModel):
    record_index: int
    field: str
    reason_code: str
    message: str
    raw_value: Any


class ValidationResult(BaseModel):
    is_valid: bool
    rejection: Optional[ValidationRejection] = None
    sanitized_flow: Optional[FlowRecord] = None


class TelemetryBatchValidationReport(BaseModel):
    total_received: int
    valid_count: int
    rejected_count: int
    valid_flows: List[FlowRecord] = Field(default_factory=list)
    rejections: List[ValidationRejection] = Field(default_factory=list)


class TelemetryValidator:
    """Production validator for network flow telemetry."""

    MIN_TIMESTAMP_EPOCH = 0.0  # Jan 1, 1970
    MAX_FUTURE_DRIFT_SECONDS = 86400 * 2  # Max 2 days in future to allow slight sensor clock drift

    @staticmethod
    def validate_ip_address(ip_str: str) -> bool:
        """Verifies if the string is a syntactically valid IPv4 or IPv6 address."""
        if not ip_str or not isinstance(ip_str, str):
            return False
        try:
            ipaddress.ip_address(ip_str.strip())
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_port(port: Any) -> bool:
        """Validates transport layer port (0-65535, integer, finite)."""
        if isinstance(port, bool):
            return False
        if not isinstance(port, (int, float)):
            return False
        if math.isnan(port) or math.isinf(port):
            return False
        int_port = int(port)
        return int_port == port and 0 <= int_port <= 65535

    @classmethod
    def validate_timestamp(cls, ts: Any) -> Tuple[bool, Optional[datetime]]:
        """Validates that a timestamp is realistic, finite, and converts to UTC datetime."""
        if ts is None:
            return True, datetime.now(timezone.utc)
        
        parsed_dt: Optional[datetime] = None
        if isinstance(ts, (int, float)):
            if math.isnan(ts) or math.isinf(ts) or ts < cls.MIN_TIMESTAMP_EPOCH:
                return False, None
            try:
                parsed_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                return False, None
        elif isinstance(ts, str):
            try:
                # Handle ISO format
                cleaned = ts.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(cleaned)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return False, None
        elif isinstance(ts, datetime):
            parsed_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            return False, None

        # Check future boundary
        now_epoch = datetime.now(timezone.utc).timestamp()
        if parsed_dt.timestamp() > now_epoch + cls.MAX_FUTURE_DRIFT_SECONDS:
            return False, None
            
        return True, parsed_dt

    @classmethod
    def validate_single_flow(cls, raw: Dict[str, Any], index: int = 0) -> ValidationResult:
        """Validates a raw flow dictionary and produces a validated FlowRecord or rejection."""
        # 1. Source IP
        src_ip = str(raw.get("src_ip") or raw.get("source_ip") or "").strip()
        if not cls.validate_ip_address(src_ip):
            return ValidationResult(
                is_valid=False,
                rejection=ValidationRejection(
                    record_index=index,
                    field="source_ip",
                    reason_code="INVALID_IP_ADDRESS",
                    message=f"Source IP '{src_ip}' is not a valid IPv4 or IPv6 address",
                    raw_value=src_ip,
                )
            )

        # 2. Destination IP
        dst_ip = str(raw.get("dst_ip") or raw.get("destination_ip") or "").strip()
        if not cls.validate_ip_address(dst_ip):
            return ValidationResult(
                is_valid=False,
                rejection=ValidationRejection(
                    record_index=index,
                    field="destination_ip",
                    reason_code="INVALID_IP_ADDRESS",
                    message=f"Destination IP '{dst_ip}' is not a valid IPv4 or IPv6 address",
                    raw_value=dst_ip,
                )
            )

        # 3. Source Port
        src_port = raw.get("src_port") if "src_port" in raw else raw.get("source_port", 0)
        if not cls.validate_port(src_port):
            return ValidationResult(
                is_valid=False,
                rejection=ValidationRejection(
                    record_index=index,
                    field="source_port",
                    reason_code="INVALID_PORT",
                    message=f"Source port '{src_port}' out of bounds [0, 65535]",
                    raw_value=src_port,
                )
            )

        # 4. Destination Port
        dst_port = raw.get("dst_port") if "dst_port" in raw else raw.get("destination_port", 0)
        if not cls.validate_port(dst_port):
            return ValidationResult(
                is_valid=False,
                rejection=ValidationRejection(
                    record_index=index,
                    field="destination_port",
                    reason_code="INVALID_PORT",
                    message=f"Destination port '{dst_port}' out of bounds [0, 65535]",
                    raw_value=dst_port,
                )
            )

        # 5. Timestamp
        valid_ts, parsed_dt = cls.validate_timestamp(raw.get("timestamp"))
        if not valid_ts or parsed_dt is None:
            return ValidationResult(
                is_valid=False,
                rejection=ValidationRejection(
                    record_index=index,
                    field="timestamp",
                    reason_code="INVALID_TIMESTAMP",
                    message="Timestamp is missing, non-finite, or outside realistic epoch range",
                    raw_value=raw.get("timestamp"),
                )
            )

        # 6. Counters (Packet, Byte, Duration) - Must be non-negative and finite
        duration_ms = raw.get("duration_ms", raw.get("flow_duration_ms", 0.0))
        packet_count = raw.get("packets", raw.get("packet_count", 1))
        byte_count = raw.get("bytes", raw.get("byte_count", 0))

        for name, val in [("duration_ms", duration_ms), ("packet_count", packet_count), ("byte_count", byte_count)]:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return ValidationResult(
                    is_valid=False,
                    rejection=ValidationRejection(
                        record_index=index,
                        field=name,
                        reason_code="INVALID_NUMERIC",
                        message=f"{name} must be a valid number",
                        raw_value=val,
                    )
                )
            if math.isnan(val) or math.isinf(val) or val < 0:
                return ValidationResult(
                    is_valid=False,
                    rejection=ValidationRejection(
                        record_index=index,
                        field=name,
                        reason_code="NEGATIVE_OR_NON_FINITE_COUNTER",
                        message=f"{name} cannot be negative, NaN or Infinity",
                        raw_value=val,
                    )
                )

        # 7. Protocol Sanitization
        raw_proto = str(raw.get("proto") or raw.get("protocol") or "TCP").strip().upper()
        if raw_proto in ("6", "TCP"):
            protocol = ProtocolEnum.TCP
        elif raw_proto in ("17", "UDP"):
            protocol = ProtocolEnum.UDP
        elif raw_proto in ("1", "ICMP", "58", "ICMPV6"):
            protocol = ProtocolEnum.ICMP
        elif raw_proto in ("47", "GRE"):
            protocol = ProtocolEnum.GRE
        else:
            protocol = ProtocolEnum.OTHER

        # 8. Direction
        raw_dir = str(raw.get("direction", "ingress")).strip().lower()
        direction = FlowDirectionEnum(raw_dir) if raw_dir in FlowDirectionEnum._value2member_map_ else FlowDirectionEnum.INGRESS

        # Rates calculation
        dur_sec = float(duration_ms) / 1000.0 if float(duration_ms) > 0 else 1.0
        pkt_rate = float(raw.get("packet_rate") or (int(packet_count) / dur_sec))
        byte_rate = float(raw.get("byte_rate") or (int(byte_count) / dur_sec))

        sanitized = FlowRecord(
            id=raw.get("id"),
            timestamp=parsed_dt,
            source_ip=src_ip,
            destination_ip=dst_ip,
            source_port=int(src_port),
            destination_port=int(dst_port),
            protocol=protocol,
            flow_duration_ms=float(duration_ms),
            packet_count=int(packet_count),
            byte_count=int(byte_count),
            packet_rate=pkt_rate,
            byte_rate=byte_rate,
            forward_packets=int(raw.get("forward_packets", int(packet_count))),
            backward_packets=int(raw.get("backward_packets", 0)),
            forward_bytes=int(raw.get("forward_bytes", int(byte_count))),
            backward_bytes=int(raw.get("backward_bytes", 0)),
            tcp_flags=str(raw.get("tcp_flags") or raw.get("flags") or ""),
            connection_state=str(raw.get("connection_state") or raw.get("state") or "ESTABLISHED"),
            direction=direction,
            metadata=raw.get("metadata", {}),
        )

        return ValidationResult(is_valid=True, sanitized_flow=sanitized)

    @classmethod
    def validate_batch(cls, raw_records: List[Dict[str, Any]]) -> TelemetryBatchValidationReport:
        """Validates an entire batch of raw telemetry records."""
        valid_flows: List[FlowRecord] = []
        rejections: List[ValidationRejection] = []

        for idx, rec in enumerate(raw_records):
            res = cls.validate_single_flow(rec, index=idx)
            if res.is_valid and res.sanitized_flow:
                valid_flows.append(res.sanitized_flow)
            elif res.rejection:
                rejections.append(res.rejection)

        return TelemetryBatchValidationReport(
            total_received=len(raw_records),
            valid_count=len(valid_flows),
            rejected_count=len(rejections),
            valid_flows=valid_flows,
            rejections=rejections,
        )
