"""Foresight AI - Comprehensive Statistical Feature Extraction Engine.

Extracts 24+ mathematical behavior features over flow arrays and temporal windows:
- Shannon Entropies: H(X) = -sum(p * log2(p))
- Volumetric and Flow Rates
- Directional ratios (Forward vs Backward)
- Packet length distributions
- TCP flag dynamics
- Burstiness and variance metrics
- Destination concentration scores
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from app.ml.contracts import FlowRecord, TemporalWindowFeatures


class NetworkFeatureExtractor:
    """Computes mathematical behavior features over network flows."""

    @staticmethod
    def calculate_shannon_entropy(items: List[Any]) -> float:
        """Calculates discrete Shannon entropy: H(X) = -sum(p_i * log2(p_i))."""
        if not items:
            return 0.0
        total = len(items)
        freq: Dict[Any, int] = {}
        for x in items:
            freq[x] = freq.get(x, 0) + 1
        
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return float(entropy)

    @classmethod
    def extract_features(
        cls,
        flows: List[FlowRecord],
        window_id: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        duration_seconds: int = 60,
        target_entity: str = "GLOBAL_PERIMETER",
    ) -> TemporalWindowFeatures:
        """Transforms an array of FlowRecord objects into dense statistical behavioral features."""
        w_id = window_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if not flows:
            start_ts = window_start or now
            end_ts = window_end or now
            return TemporalWindowFeatures(
                window_id=w_id,
                window_start=start_ts,
                window_end=end_ts,
                duration_seconds=duration_seconds,
                target_entity=target_entity,
                vector=[0.0] * 28,
            )

        timestamps = [f.timestamp for f in flows]
        start_ts = window_start or min(timestamps)
        end_ts = window_end or max(timestamps)
        
        effective_duration = max(1.0, float(duration_seconds))
        flow_vol = len(flows)
        pkt_vol = sum(f.packet_count for f in flows)
        byte_vol = sum(f.byte_count for f in flows)

        pkts_per_sec = float(pkt_vol) / effective_duration
        bytes_per_sec = float(byte_vol) / effective_duration

        # Durations
        durations = [f.flow_duration_ms for f in flows]
        mean_duration = float(np.mean(durations)) if durations else 0.0
        duration_var = float(np.var(durations)) if len(durations) > 1 else 0.0

        # Directional Metrics
        fwd_pkts = sum(f.forward_packets for f in flows)
        bwd_pkts = sum(f.backward_packets for f in flows)
        fwd_bytes = sum(f.forward_bytes for f in flows)
        bwd_bytes = sum(f.backward_bytes for f in flows)
        
        fwd_bwd_ratio = float(fwd_pkts) / float(bwd_pkts) if bwd_pkts > 0 else float(fwd_pkts or 1.0)

        # Packet Length Distribution (derived from byte/packet ratio per flow)
        pkt_lengths: List[float] = []
        for f in flows:
            if f.packet_count > 0:
                pkt_lengths.append(float(f.byte_count) / float(f.packet_count))
            else:
                pkt_lengths.append(0.0)

        mean_pkt_len = float(np.mean(pkt_lengths)) if pkt_lengths else 0.0
        std_pkt_len = float(np.std(pkt_lengths)) if len(pkt_lengths) > 1 else 0.0
        min_pkt_len = float(np.min(pkt_lengths)) if pkt_lengths else 0.0
        max_pkt_len = float(np.max(pkt_lengths)) if pkt_lengths else 0.0

        # TCP Flag Dynamics
        syn_cnt = 0
        ack_cnt = 0
        rst_cnt = 0
        fin_cnt = 0
        for f in flows:
            flags = (f.tcp_flags or "").upper()
            if "SYN" in flags:
                syn_cnt += 1
            if "ACK" in flags:
                ack_cnt += 1
            if "RST" in flags:
                rst_cnt += 1
            if "FIN" in flags:
                fin_cnt += 1

        syn_rate = float(syn_cnt) / effective_duration
        ack_rate = float(ack_cnt) / effective_duration
        rst_rate = float(rst_cnt) / effective_duration
        fin_rate = float(fin_cnt) / effective_duration
        syn_ack_ratio = float(syn_cnt) / float(ack_cnt) if ack_cnt > 0 else float(syn_cnt)
        rst_ratio = float(rst_cnt) / float(flow_vol) if flow_vol > 0 else 0.0

        # Diversity & Entity Collections
        src_ips = [f.source_ip for f in flows]
        dst_ips = [f.destination_ip for f in flows]
        src_ports = [f.source_port for f in flows]
        dst_ports = [f.destination_port for f in flows]

        uniq_src_ips = len(set(src_ips))
        uniq_dst_ips = len(set(dst_ips))
        uniq_src_ports = len(set(src_ports))
        uniq_dst_ports = len(set(dst_ports))

        # Shannon Entropies
        entropy_src_ip = cls.calculate_shannon_entropy(src_ips)
        entropy_dst_ip = cls.calculate_shannon_entropy(dst_ips)
        entropy_src_port = cls.calculate_shannon_entropy(src_ports)
        entropy_dst_port = cls.calculate_shannon_entropy(dst_ports)

        # Burstiness & Variance
        pkt_rates = [f.packet_rate or 0.0 for f in flows]
        byte_rates = [f.byte_rate or 0.0 for f in flows]
        pkt_rate_var = float(np.var(pkt_rates)) if len(pkt_rates) > 1 else 0.0
        byte_rate_var = float(np.var(byte_rates)) if len(byte_rates) > 1 else 0.0

        # Burst score: normalized ratio of peak packet rate to mean packet rate
        max_rate = max(pkt_rates) if pkt_rates else 0.0
        mean_rate = np.mean(pkt_rates) if pkt_rates else 1.0
        burst_score = float(max_rate / (mean_rate + 1e-5))

        # Connection Behavior: Concentration & Repeated Destinations
        dst_counts = {}
        for d in dst_ips:
            dst_counts[d] = dst_counts.get(d, 0) + 1
        
        top_dst_count = max(dst_counts.values()) if dst_counts else 0
        dst_concentration = float(top_dst_count) / float(flow_vol) if flow_vol > 0 else 0.0
        repeated_dst_ratio = 1.0 - (float(uniq_dst_ips) / float(flow_vol)) if flow_vol > 0 else 0.0

        # Assemble Dense Feature Vector for ML
        vector = [
            float(flow_vol),
            float(pkt_vol),
            float(byte_vol),
            float(pkts_per_sec),
            float(bytes_per_sec),
            float(mean_duration),
            float(duration_var),
            float(fwd_pkts),
            float(bwd_pkts),
            float(fwd_bytes),
            float(bwd_bytes),
            float(fwd_bwd_ratio),
            float(mean_pkt_len),
            float(std_pkt_len),
            float(syn_cnt),
            float(syn_rate),
            float(ack_cnt),
            float(rst_cnt),
            float(syn_ack_ratio),
            float(rst_ratio),
            float(uniq_src_ips),
            float(uniq_dst_ips),
            float(uniq_src_ports),
            float(uniq_dst_ports),
            float(entropy_src_ip),
            float(entropy_dst_ip),
            float(entropy_src_port),
            float(entropy_dst_port),
        ]

        return TemporalWindowFeatures(
            window_id=w_id,
            window_start=start_ts,
            window_end=end_ts,
            duration_seconds=duration_seconds,
            target_entity=target_entity,
            flow_volume=flow_vol,
            packet_volume=pkt_vol,
            byte_volume=byte_vol,
            packets_per_second=round(pkts_per_sec, 4),
            bytes_per_second=round(bytes_per_sec, 4),
            mean_flow_duration_ms=round(mean_duration, 4),
            duration_variance=round(duration_var, 4),
            forward_packets_total=fwd_pkts,
            backward_packets_total=bwd_pkts,
            forward_bytes_total=fwd_bytes,
            backward_bytes_total=bwd_bytes,
            forward_backward_ratio=round(fwd_bwd_ratio, 4),
            mean_packet_length=round(mean_pkt_len, 4),
            packet_length_std=round(std_pkt_len, 4),
            min_packet_length=round(min_pkt_len, 4),
            max_packet_length=round(max_pkt_len, 4),
            syn_count=syn_cnt,
            syn_rate=round(syn_rate, 4),
            ack_count=ack_cnt,
            ack_rate=round(ack_rate, 4),
            rst_count=rst_cnt,
            rst_rate=round(rst_rate, 4),
            fin_count=fin_cnt,
            fin_rate=round(fin_rate, 4),
            syn_ack_ratio=round(syn_ack_ratio, 4),
            rst_ratio=round(rst_ratio, 4),
            unique_source_ips=uniq_src_ips,
            unique_destination_ips=uniq_dst_ips,
            unique_source_ports=uniq_src_ports,
            unique_destination_ports=uniq_dst_ports,
            entropy_source_ips=round(entropy_src_ip, 4),
            entropy_dest_ips=round(entropy_dst_ip, 4),
            entropy_source_ports=round(entropy_src_port, 4),
            entropy_dest_ports=round(entropy_dst_port, 4),
            packet_rate_variance=round(pkt_rate_var, 4),
            byte_rate_variance=round(byte_rate_var, 4),
            traffic_burst_score=round(burst_score, 4),
            new_connections_count=syn_cnt,
            repeated_destinations_ratio=round(repeated_dst_ratio, 4),
            destination_concentration_score=round(dst_concentration, 4),
            vector=[round(x, 4) for x in vector],
        )
