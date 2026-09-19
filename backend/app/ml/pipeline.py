"""Foresight AI - Pipeline Architecture & Baseline Telemetry Normalizer."""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from app.core.logging import logger
from app.ml.base import BaseFeatureExtractor, BaseTelemetryNormalizer
from app.ml.contracts import (
    FlowDirectionEnum,
    FlowRecord,
    ProtocolEnum,
    TemporalWindowFeatures,
)


class StandardTelemetryNormalizer(BaseTelemetryNormalizer):
    """Production-grade telemetry normalizer with field validation and fallback adapters."""

    def normalize(self, raw_data: Dict[str, Any]) -> FlowRecord:
        # Standardize Protocol
        raw_proto = str(raw_data.get("proto") or raw_data.get("protocol") or "TCP").upper()
        if raw_proto in ("6", "TCP"):
            protocol = ProtocolEnum.TCP
        elif raw_proto in ("17", "UDP"):
            protocol = ProtocolEnum.UDP
        elif raw_proto in ("1", "ICMP"):
            protocol = ProtocolEnum.ICMP
        elif raw_proto in ("47", "GRE"):
            protocol = ProtocolEnum.GRE
        else:
            protocol = ProtocolEnum.OTHER

        # Standardize Source & Destination
        source_ip = str(raw_data.get("src_ip") or raw_data.get("source_ip") or "127.0.0.1")
        destination_ip = str(raw_data.get("dst_ip") or raw_data.get("destination_ip") or "127.0.0.1")
        source_port = int(raw_data.get("src_port") or raw_data.get("source_port") or 0)
        destination_port = int(raw_data.get("dst_port") or raw_data.get("destination_port") or 0)

        # Standardize Metrics
        duration_ms = float(raw_data.get("duration_ms") or raw_data.get("flow_duration_ms") or 0.0)
        packet_count = int(raw_data.get("packets") or raw_data.get("packet_count") or 1)
        byte_count = int(raw_data.get("bytes") or raw_data.get("byte_count") or 0)
        
        # Calculate rates if duration is positive
        sec = duration_ms / 1000.0 if duration_ms > 0 else 1.0
        packet_rate = float(raw_data.get("packet_rate") or (packet_count / sec))
        byte_rate = float(raw_data.get("byte_rate") or (byte_count / sec))

        # Direction
        direction_str = str(raw_data.get("direction", "ingress")).lower()
        direction = FlowDirectionEnum(direction_str) if direction_str in FlowDirectionEnum._value2member_map_ else FlowDirectionEnum.INGRESS

        # Timestamp
        ts = raw_data.get("timestamp")
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        elif isinstance(ts, (int, float)):
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now(timezone.utc)

        return FlowRecord(
            timestamp=timestamp,
            source_ip=source_ip,
            destination_ip=destination_ip,
            source_port=source_port,
            destination_port=destination_port,
            protocol=protocol,
            flow_duration_ms=duration_ms,
            packet_count=packet_count,
            byte_count=byte_count,
            packet_rate=packet_rate,
            byte_rate=byte_rate,
            tcp_flags=str(raw_data.get("tcp_flags") or raw_data.get("flags") or ""),
            connection_state=str(raw_data.get("state") or raw_data.get("connection_state") or "ESTABLISHED"),
            direction=direction,
            metadata=raw_data.get("metadata", {}),
        )

    def batch_normalize(self, raw_records: List[Dict[str, Any]]) -> List[FlowRecord]:
        return [self.normalize(record) for record in raw_records]


class StatisticalFeatureExtractor(BaseFeatureExtractor):
    """Computes Shannon entropy, volumetric distributions, and flag ratios over flow windows."""

    def _calculate_entropy(self, items: List[Any]) -> float:
        if not items:
            return 0.0
        total = len(items)
        freq: Dict[Any, int] = {}
        for item in items:
            freq[item] = freq.get(item, 0) + 1
        entropy = 0.0
        for count in freq.values():
            p = count / total
            entropy -= p * math.log2(p)
        return float(entropy)

    def extract_window_features(
        self, flows: List[FlowRecord], window_duration_seconds: int = 60
    ) -> TemporalWindowFeatures:
        window_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        if not flows:
            return TemporalWindowFeatures(
                window_id=window_id,
                window_start=now,
                window_end=now,
                duration_seconds=window_duration_seconds,
                flow_volume=0,
                packet_volume=0,
                byte_volume=0,
                unique_source_ips=0,
                unique_destination_ports=0,
                syn_ack_ratio=0.0,
                rst_ratio=0.0,
                mean_flow_duration_ms=0.0,
                entropy_dest_ports=0.0,
                entropy_source_ips=0.0,
                vector=[0.0] * 10,
            )

        timestamps = [f.timestamp for f in flows]
        window_start = min(timestamps)
        window_end = max(timestamps)
        
        flow_vol = len(flows)
        pkt_vol = sum(f.packet_count for f in flows)
        byte_vol = sum(f.byte_count for f in flows)
        
        src_ips = [f.source_ip for f in flows]
        dst_ports = [f.destination_port for f in flows]
        
        unique_src = len(set(src_ips))
        unique_dst_ports = len(set(dst_ports))
        
        syn_count = sum(1 for f in flows if "SYN" in (f.tcp_flags or "").upper())
        rst_count = sum(1 for f in flows if "RST" in (f.tcp_flags or "").upper())
        
        syn_ratio = syn_count / flow_vol if flow_vol > 0 else 0.0
        rst_ratio = rst_count / flow_vol if flow_vol > 0 else 0.0
        mean_duration = sum(f.flow_duration_ms for f in flows) / flow_vol if flow_vol > 0 else 0.0
        
        entropy_dst = self._calculate_entropy(dst_ports)
        entropy_src = self._calculate_entropy(src_ips)
        
        feature_vector = [
            float(flow_vol),
            float(pkt_vol),
            float(byte_vol),
            float(unique_src),
            float(unique_dst_ports),
            float(syn_ratio),
            float(rst_ratio),
            float(mean_duration),
            float(entropy_dst),
            float(entropy_src),
        ]

        return TemporalWindowFeatures(
            window_id=window_id,
            window_start=window_start,
            window_end=window_end,
            duration_seconds=window_duration_seconds,
            flow_volume=flow_vol,
            packet_volume=pkt_vol,
            byte_volume=byte_vol,
            unique_source_ips=unique_src,
            unique_destination_ports=unique_dst_ports,
            syn_ack_ratio=syn_ratio,
            rst_ratio=rst_ratio,
            mean_flow_duration_ms=mean_duration,
            entropy_dest_ports=entropy_dst,
            entropy_source_ips=entropy_src,
            vector=feature_vector,
        )
