"""Foresight AI - Comprehensive Automated Test Suite for Telemetry Ingestion Engine (Step 2).

Tests:
1. Strict IP, Port, Timestamp, Counter Validation (IPv4, IPv6, NaN, Inf, Negatives)
2. Batch Validation & Partial Failure Resilience
3. Deterministic Flow Hashing & Deduplication
4. Bidirectional Flow Reconstruction & Forward/Backward Tracking
5. Inactivity-Based Flow Expiration & Timeout Eviction
6. Mathematical Feature Extractor (Shannon Entropy, Burst Score, Ratios)
7. Sliding Temporal Window Generation & Temporal Leakage Protection
8. Future Multi-Horizon Target Alignment
9. Real PCAP / PCAPNG Parsing with Scapy (Synthetic Packet Synthesis)
10. Asynchronous Ingestion Job System & Path Traversal Security
11. Telemetry Quality Tracking & API Endpoints
"""

from datetime import datetime, timedelta, timezone
import math
import os
import tempfile
import pytest
from httpx import AsyncClient
from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.utils import PcapWriter
from app.ml.contracts import (
    FlowDirectionEnum,
    FlowRecord,
    ProtocolEnum,
)
from app.telemetry.deduplication import TelemetryDeduplicator
from app.telemetry.feature_extractor import NetworkFeatureExtractor
from app.telemetry.flow_reconstructor import BidirectionalFlowReconstructor
from app.telemetry.job_manager import JobStatus, TelemetryJobManager
from app.telemetry.label_alignment import FutureLabelAligner
from app.telemetry.pcap_parser import PcapStreamParser
from app.telemetry.quality_service import TelemetryQualityTracker
from app.telemetry.validation import TelemetryValidator
from app.telemetry.window_generator import SlidingWindowGenerator


# ==============================================================================
# 1. VALIDATION & SANITIZATION TESTS
# ==============================================================================

def test_ip_and_port_validation():
    # IPv4 & IPv6 Valid Cases
    assert TelemetryValidator.validate_ip_address("192.168.1.1") is True
    assert TelemetryValidator.validate_ip_address("10.0.0.254") is True
    assert TelemetryValidator.validate_ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334") is True
    assert TelemetryValidator.validate_ip_address("::1") is True

    # Invalid IPs
    assert TelemetryValidator.validate_ip_address("999.999.999.999") is False
    assert TelemetryValidator.validate_ip_address("not_an_ip") is False
    assert TelemetryValidator.validate_ip_address("") is False

    # Port Validation
    assert TelemetryValidator.validate_port(80) is True
    assert TelemetryValidator.validate_port(0) is True
    assert TelemetryValidator.validate_port(65535) is True
    assert TelemetryValidator.validate_port(-1) is False
    assert TelemetryValidator.validate_port(65536) is False
    assert TelemetryValidator.validate_port(float("nan")) is False
    assert TelemetryValidator.validate_port("80") is False  # strict int/float


def test_counter_and_timestamp_validation():
    # Negative and non-finite counters
    res_neg = TelemetryValidator.validate_single_flow({
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 1234,
        "dst_port": 80,
        "packet_count": -10,  # Negative
    })
    assert res_neg.is_valid is False
    assert res_neg.rejection.reason_code == "NEGATIVE_OR_NON_FINITE_COUNTER"

    res_nan = TelemetryValidator.validate_single_flow({
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 1234,
        "dst_port": 80,
        "byte_count": float("nan"),  # NaN
    })
    assert res_nan.is_valid is False
    assert res_nan.rejection.reason_code == "NEGATIVE_OR_NON_FINITE_COUNTER"

    # Future drift boundary
    impossible_future_ts = datetime.now(timezone.utc) + timedelta(days=10)
    res_future = TelemetryValidator.validate_single_flow({
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 1234,
        "dst_port": 80,
        "timestamp": impossible_future_ts.isoformat(),
    })
    assert res_future.is_valid is False
    assert res_future.rejection.reason_code == "INVALID_TIMESTAMP"


def test_batch_validation_partial_failure():
    batch = [
        # Valid flow 1
        {"src_ip": "192.168.1.10", "dst_ip": "10.0.0.1", "src_port": 4000, "dst_port": 443, "packets": 10, "bytes": 1000},
        # Malformed IP
        {"src_ip": "bad_ip_address", "dst_ip": "10.0.0.1", "src_port": 4001, "dst_port": 443, "packets": 10, "bytes": 1000},
        # Port out of bounds
        {"src_ip": "192.168.1.11", "dst_ip": "10.0.0.1", "src_port": 70000, "dst_port": 443, "packets": 10, "bytes": 1000},
        # Valid flow 2
        {"src_ip": "192.168.1.12", "dst_ip": "10.0.0.1", "src_port": 4002, "dst_port": 80, "packets": 5, "bytes": 500},
    ]
    report = TelemetryValidator.validate_batch(batch)
    assert report.total_received == 4
    assert report.valid_count == 2
    assert report.rejected_count == 2
    assert len(report.valid_flows) == 2
    assert report.rejections[0].field == "source_ip"
    assert report.rejections[1].field == "source_port"


# ==============================================================================
# 2. DEDUPLICATION TESTS
# ==============================================================================

def test_deduplication_engine():
    dedup = TelemetryDeduplicator()
    now = datetime.now(timezone.utc)
    
    flow_a = FlowRecord(
        timestamp=now,
        source_ip="192.168.1.5",
        destination_ip="10.0.0.1",
        source_port=5000,
        destination_port=443,
        protocol=ProtocolEnum.TCP,
        packet_count=10,
        byte_count=1500,
        tcp_flags="SYN,ACK",
    )
    # Exact duplicate
    flow_a_dup = FlowRecord(
        timestamp=now,
        source_ip="192.168.1.5",
        destination_ip="10.0.0.1",
        source_port=5000,
        destination_port=443,
        protocol=ProtocolEnum.TCP,
        packet_count=10,
        byte_count=1500,
        tcp_flags="SYN,ACK",
    )
    # Distinct flow
    flow_b = FlowRecord(
        timestamp=now,
        source_ip="192.168.1.6",
        destination_ip="10.0.0.1",
        source_port=5001,
        destination_port=443,
        protocol=ProtocolEnum.TCP,
        packet_count=20,
        byte_count=3000,
    )

    unique, dup_cnt = dedup.filter_duplicates([flow_a, flow_a_dup, flow_b])
    assert len(unique) == 2
    assert dup_cnt == 1
    assert unique[0].source_ip == "192.168.1.5"
    assert unique[1].source_ip == "192.168.1.6"


# ==============================================================================
# 3. BIDIRECTIONAL FLOW RECONSTRUCTION & TIMEOUT TESTS
# ==============================================================================

def test_bidirectional_flow_reconstruction():
    reconstructor = BidirectionalFlowReconstructor(idle_timeout_seconds=30.0)
    base_time = datetime.now(timezone.utc)

    # 1. Forward packet (Initiator -> Responder: SYN)
    reconstructor.process_packet(
        timestamp=base_time,
        src_ip="192.168.1.100",
        dst_ip="10.0.0.50",
        src_port=49152,
        dst_port=443,
        protocol=ProtocolEnum.TCP,
        packet_len=64,
        tcp_flags="SYN",
    )

    # 2. Backward packet (Responder -> Initiator: SYN, ACK)
    reconstructor.process_packet(
        timestamp=base_time + timedelta(milliseconds=10),
        src_ip="10.0.0.50",
        dst_ip="192.168.1.100",
        src_port=443,
        dst_port=49152,
        protocol=ProtocolEnum.TCP,
        packet_len=64,
        tcp_flags="SYN,ACK",
    )

    # 3. Forward packet (Data)
    reconstructor.process_packet(
        timestamp=base_time + timedelta(milliseconds=20),
        src_ip="192.168.1.100",
        dst_ip="10.0.0.50",
        src_port=49152,
        dst_port=443,
        protocol=ProtocolEnum.TCP,
        packet_len=1400,
        tcp_flags="ACK,PSH",
    )

    assert reconstructor.active_flows_count == 1
    flows = reconstructor.flush_all()
    assert len(flows) == 1
    flow = flows[0]

    assert flow.source_ip == "192.168.1.100"
    assert flow.destination_ip == "10.0.0.50"
    assert flow.packet_count == 3
    assert flow.forward_packets == 2
    assert flow.backward_packets == 1
    assert flow.forward_bytes == 1464
    assert flow.backward_bytes == 64
    assert flow.byte_count == 1528
    assert "SYN" in flow.tcp_flags
    assert "ACK" in flow.tcp_flags
    assert "PSH" in flow.tcp_flags


def test_flow_inactivity_timeout():
    reconstructor = BidirectionalFlowReconstructor(idle_timeout_seconds=10.0)
    t0 = datetime.now(timezone.utc)

    reconstructor.process_packet(
        timestamp=t0,
        src_ip="10.0.0.1",
        dst_ip="10.0.0.2",
        src_port=1000,
        dst_port=80,
        protocol=ProtocolEnum.TCP,
        packet_len=100,
    )
    assert reconstructor.active_flows_count == 1

    # Check eviction after 5 seconds (under 10s idle timeout -> not evicted)
    evicted_5s = reconstructor.evict_timed_out_flows(t0 + timedelta(seconds=5))
    assert len(evicted_5s) == 0
    assert reconstructor.active_flows_count == 1

    # Check eviction after 11 seconds (over 10s idle timeout -> evicted)
    evicted_11s = reconstructor.evict_timed_out_flows(t0 + timedelta(seconds=11))
    assert len(evicted_11s) == 1
    assert reconstructor.active_flows_count == 0
    assert evicted_11s[0].source_ip == "10.0.0.1"


# ==============================================================================
# 4. MATHEMATICAL FEATURE EXTRACTOR TESTS
# ==============================================================================

def test_statistical_feature_extractor():
    base_t = datetime.now(timezone.utc)
    flows = [
        FlowRecord(
            timestamp=base_t + timedelta(seconds=i),
            source_ip=f"192.168.1.{10 + (i % 3)}",  # 3 unique IPs
            destination_ip="10.0.0.1",
            source_port=1000 + i,
            destination_port=443 if i < 8 else 80,  # 2 unique ports
            protocol=ProtocolEnum.TCP,
            flow_duration_ms=100.0,
            packet_count=10,
            byte_count=5000,
            forward_packets=6,
            backward_packets=4,
            forward_bytes=3000,
            backward_bytes=2000,
            tcp_flags="SYN,ACK" if i % 2 == 0 else "ACK",
        )
        for i in range(10)
    ]

    features = NetworkFeatureExtractor.extract_features(flows, duration_seconds=60)
    assert features.flow_volume == 10
    assert features.packet_volume == 100
    assert features.byte_volume == 50000
    assert features.unique_source_ips == 3
    assert features.unique_destination_ports == 2
    assert features.unique_destination_ips == 1
    assert features.forward_packets_total == 60
    assert features.backward_packets_total == 40
    assert features.forward_bytes_total == 30000
    assert features.backward_bytes_total == 20000
    assert features.forward_backward_ratio == 1.5
    assert features.entropy_source_ips > 0.0
    assert features.entropy_dest_ports > 0.0
    assert features.entropy_dest_ips == 0.0  # Only 1 dest IP -> zero entropy
    assert len(features.vector) == 28


# ==============================================================================
# 5. SLIDING TEMPORAL WINDOWS & LEAKAGE PROTECTION TESTS
# ==============================================================================

def test_sliding_temporal_window_generator_and_leakage_protection():
    generator = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    t0 = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Create flows spaced across 120 seconds
    flows = [
        FlowRecord(
            timestamp=t0 + timedelta(seconds=sec),
            source_ip="192.168.1.1",
            destination_ip="10.0.0.1",
            source_port=5000,
            destination_port=80,
            packet_count=1,
            byte_count=100,
        )
        for sec in [10, 25, 45, 70, 95, 110]
    ]

    windows = generator.generate_windows_from_flows(flows)
    assert len(windows) >= 3

    # Window 1: [12:00:10, 12:01:10) -> Should contain flows at sec 10, 25, 45 (3 flows)
    # Flows at sec 70, 95, 110 are in future and must NOT leak into Window 1
    w1 = windows[0]
    assert w1.flow_volume == 3
    assert w1.window_start == t0 + timedelta(seconds=10)

    # Window 2: [12:00:40, 12:01:40) -> Should contain flows at sec 45, 70, 95 (3 flows)
    w2 = windows[1]
    assert w2.flow_volume == 3


def test_future_label_alignment():
    w = NetworkFeatureExtractor.extract_features(
        [],
        window_start=datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 9, 18, 12, 1, 0, tzinfo=timezone.utc),
        duration_seconds=60,
    )

    # Synthetic ground truth event at 12:08:00 (7 minutes after window_end -> inside 15m horizon, outside 5m horizon)
    events = [
        {
            "timestamp": datetime(2026, 9, 18, 12, 8, 0, tzinfo=timezone.utc),
            "threat_type": "SYN Flood DDoS",
            "severity": "HIGH",
        }
    ]

    target = FutureLabelAligner.align_window_with_future_labels(w, events)
    assert target.horizon_5m_attack_occurred is False
    assert target.horizon_5m_threat == "BENIGN"
    assert target.horizon_15m_attack_occurred is True
    assert target.horizon_15m_threat == "SYN Flood DDoS"
    assert target.horizon_30m_attack_occurred is True
    assert target.horizon_60m_attack_occurred is True


# ==============================================================================
# 6. SCAPY PCAP PARSING & PACKET EXTRACTION
# ==============================================================================

def test_pcap_parsing_real_scapy():
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
        pcap_path = tmp_file.name

    try:
        # Synthesize real packets using Scapy
        t0 = datetime.now(timezone.utc).timestamp()
        from scapy.layers.l2 import Ether
        mac_src = "00:11:22:33:44:55"
        mac_dst = "aa:bb:cc:dd:ee:ff"
        packets = [
            # TCP SYN packet
            Ether(src=mac_src, dst=mac_dst) / IP(src="192.168.1.10", dst="10.0.0.1") / TCP(sport=5001, dport=80, flags="S"),
            # TCP SYN-ACK reply
            Ether(src=mac_dst, dst=mac_src) / IP(src="10.0.0.1", dst="192.168.1.10") / TCP(sport=80, dport=5001, flags="SA"),
            # UDP packet
            Ether(src=mac_src, dst=mac_dst) / IP(src="192.168.1.20", dst="10.0.0.2") / UDP(sport=6000, dport=53) / b"DNS_QUERY",
            # ICMP Echo Request
            Ether(src=mac_src, dst=mac_dst) / IP(src="192.168.1.30", dst="10.0.0.3") / ICMP(type=8, code=0),
            # IPv6 TCP packet
            Ether(src=mac_src, dst=mac_dst) / IPv6(src="2001:db8::1", dst="2001:db8::2") / TCP(sport=7000, dport=443, flags="PA"),
        ]

        writer = PcapWriter(pcap_path, append=False, sync=True)
        for p in packets:
            p.time = t0
            writer.write(p)
            t0 += 0.05
        writer.close()

        # Parse with PcapStreamParser
        parser = PcapStreamParser()
        flows, stats = parser.parse_pcap_file(pcap_path)

        assert stats.packets_read == 5
        assert stats.packets_ipv4 == 4
        assert stats.packets_ipv6 == 1
        assert stats.packets_tcp == 3
        assert stats.packets_udp == 1
        assert stats.packets_icmp == 1
        assert len(flows) >= 3

        # Verify TCP flow reconstruction
        tcp_flow = next(f for f in flows if f.protocol == ProtocolEnum.TCP and f.source_ip == "192.168.1.10")
        assert tcp_flow.destination_port == 80
        assert tcp_flow.packet_count == 2
        assert "SYN" in tcp_flow.tcp_flags
        assert "ACK" in tcp_flow.tcp_flags

    finally:
        try:
            if os.path.exists(pcap_path):
                os.remove(pcap_path)
        except Exception:
            pass


# ==============================================================================
# 7. ASYNCHRONOUS JOB SYSTEM & SECURITY TESTS
# ==============================================================================

def test_pcap_job_security_and_lifecycle():
    mgr = TelemetryJobManager()

    # 1. Path traversal defense in filename
    sanitized = mgr.sanitize_filename("../../../etc/shadow.pcap")
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert sanitized == "shadow.pcap"

    # 2. Reject disallowed extensions (.exe, .sh)
    with pytest.raises(ValueError, match="Unsupported file extension"):
        mgr.create_job("malicious_script.sh", 1024)

    # 3. Reject oversized file
    with pytest.raises(ValueError, match="exceeds limit"):
        mgr.create_job("huge_file.pcap", 100 * 1024 * 1024)

    # 4. Valid Job creation
    job = mgr.create_job("legit_traffic.pcap", 2048)
    assert job.status == JobStatus.QUEUED
    assert mgr.get_job(job.job_id) is not None


# ==============================================================================
# 8. TELEMETRY EXTENDED API INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_telemetry_batch_and_quality_api(async_client: AsyncClient):
    # Test POST /telemetry/flows/batch with mixed valid and invalid records
    payload = {
        "source_identifier": "gateway-probe-01",
        "raw_records": [
            {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "src_port": 1234, "dst_port": 443, "packets": 15, "bytes": 9000},
            {"src_ip": "invalid_ip", "dst_ip": "10.0.0.2", "src_port": 1235, "dst_port": 443, "packets": 15, "bytes": 9000},
        ],
    }
    res = await async_client.post("/api/v1/telemetry/flows/batch", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert data["records_received"] == 2
    assert data["records_valid"] == 1
    assert data["records_rejected"] == 1
    assert len(data["rejections"]) == 1
    assert data["rejections"][0]["reason_code"] == "INVALID_IP_ADDRESS"

    # Test GET /telemetry/quality
    q_res = await async_client.get("/api/v1/telemetry/quality")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["total_records_ingested"] >= 2
    assert len(q_data["rejection_reasons"]) >= 1

    # Test GET /telemetry/windows
    win_res = await async_client.get("/api/v1/telemetry/windows?window_size_seconds=60&stride_seconds=30")
    assert win_res.status_code == 200
    win_data = win_res.json()
    assert "window_count" in win_data
    assert "windows" in win_data
