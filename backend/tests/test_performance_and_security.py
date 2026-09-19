"""Foresight AI - Performance Benchmarking & Defensive Security Test Suite (Step 2).

Measures actual observed performance metrics:
- Records / sec throughput
- Feature extraction latency
- Temporal window aggregation latency
- Corrupted / empty PCAP handling
- Oversized payload & malformed JSON security
"""

import math
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.ml.contracts import FlowRecord, ProtocolEnum
from app.telemetry.feature_extractor import NetworkFeatureExtractor
from app.telemetry.pcap_parser import PcapStreamParser
from app.telemetry.validation import TelemetryValidator
from app.telemetry.window_generator import SlidingWindowGenerator


def test_telemetry_performance_benchmark():
    """Measures actual processing speed on a realistic batch of 1,000 flows."""
    base_time = datetime.now(timezone.utc)
    raw_records = [
        {
            "src_ip": f"192.168.{(i % 250) + 1}.{(i % 254) + 1}",
            "dst_ip": "10.0.0.50",
            "src_port": 1024 + (i % 60000),
            "dst_port": 443 if i % 3 == 0 else (80 if i % 3 == 1 else 22),
            "proto": "TCP" if i % 4 != 0 else "UDP",
            "duration_ms": float(20 + (i % 500)),
            "packets": 5 + (i % 50),
            "bytes": 500 + (i % 10000),
            "flags": "SYN,ACK" if i % 2 == 0 else "ACK",
            "timestamp": (base_time + timedelta(milliseconds=i * 50)).isoformat(),
        }
        for i in range(1000)
    ]

    # 1. Measure Validation & Normalization Latency
    t0 = time.perf_counter()
    report = TelemetryValidator.validate_batch(raw_records)
    t_val = time.perf_counter() - t0
    val_throughput = len(raw_records) / t_val

    assert report.valid_count == 1000
    assert report.rejected_count == 0
    print(f"\n[BENCHMARK] Validation Throughput: {val_throughput:.2f} records/sec (took {t_val*1000:.2f}ms for 1000 records)")

    # 2. Measure Feature Extraction Latency
    t1 = time.perf_counter()
    features = NetworkFeatureExtractor.extract_features(report.valid_flows, duration_seconds=60)
    t_feat = time.perf_counter() - t1
    print(f"[BENCHMARK] 28-Feature Extraction Latency: {t_feat*1000:.2f}ms for 1000 flows")

    assert features.flow_volume == 1000
    assert len(features.vector) == 28
    assert t_feat < 0.20  # Under 200ms

    # 3. Measure Sliding Window Generation Latency
    generator = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    t2 = time.perf_counter()
    windows = generator.generate_windows_from_flows(report.valid_flows)
    t_win = time.perf_counter() - t2
    print(f"[BENCHMARK] Temporal Window Slicing Latency: {t_win*1000:.2f}ms ({len(windows)} windows generated)")

    assert len(windows) >= 1
    assert t_win < 0.20


def test_corrupted_and_empty_pcap_handling():
    """Defensively tests that corrupted, truncated, and empty PCAP files fail safely without crashing."""
    parser = PcapStreamParser()

    # 1. Empty file
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as f_empty:
        empty_path = f_empty.name
    try:
        flows, stats = parser.parse_pcap_file(empty_path)
        assert flows == []
        assert stats.packets_read == 0
    finally:
        try:
            if os.path.exists(empty_path):
                os.remove(empty_path)
        except Exception:
            pass

    # 2. Corrupted binary junk
    junk_path = os.path.join(tempfile.gettempdir(), f"corrupted_{int(time.time())}.pcap")
    with open(junk_path, "wb") as f_junk:
        f_junk.write(b"\xde\xad\xbe\xef\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99")
    
    try:
        with pytest.raises(Exception):
            parser.parse_pcap_file(junk_path)
    finally:
        try:
            if os.path.exists(junk_path):
                os.remove(junk_path)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_oversized_and_malformed_api_payloads(async_client: AsyncClient):
    """Tests that oversized batch requests are rejected by schema guardrails."""
    # Build batch exceeding MAX_BATCH_FLOW_RECORDS (5001 items)
    oversized = [
        {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "src_port": 80, "dst_port": 80}
        for _ in range(5001)
    ]
    res = await async_client.post("/api/v1/telemetry/flows/batch", json={
        "source_identifier": "stress-test-probe",
        "raw_records": oversized,
    })
    assert res.status_code in (413, 422)
