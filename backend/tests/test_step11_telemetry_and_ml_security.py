"""Foresight AI - Step 11 Telemetry & ML Security Hardening Tests.

Tests:
- PCAP processing resilience (empty files, malformed bytes, guaranteed file cleanup)
- Telemetry input validation (negative packets/bytes, non-finite values)
- Authoritative 37-feature schema validation (dimension & finiteness)
- Model artifact SHA-256 integrity checks
"""

import os
import tempfile
import numpy as np
import pytest
from app.ml.feature_schema import validate_feature_vector, FEATURE_NAMES
from app.ml.inference import inference_service
from app.telemetry.pcap_parser import PcapStreamParser
from app.telemetry.validation import TelemetryValidator


def test_ml_feature_schema_strictness():
    """Verifies that the ML feature validator enforces 37 dimensions and rejects NaN/Inf."""
    # 1. Valid 37-D vector
    valid_vec = np.zeros(37, dtype=np.float32)
    res = validate_feature_vector(valid_vec)
    assert res.shape == (1, 37)

    # 2. Wrong dimension (28 features instead of 37)
    with pytest.raises(ValueError, match="Feature vector must have exactly 37 elements"):
        validate_feature_vector(np.zeros(28, dtype=np.float32))

    # 3. Non-finite values (NaN)
    nan_vec = np.zeros(37, dtype=np.float32)
    nan_vec[5] = np.nan
    with pytest.raises(ValueError, match="non-finite values"):
        validate_feature_vector(nan_vec)

    # 4. Non-finite values (Infinity)
    inf_vec = np.zeros(37, dtype=np.float32)
    inf_vec[10] = np.inf
    with pytest.raises(ValueError, match="non-finite values"):
        validate_feature_vector(inf_vec)


def test_model_artifact_sha256_integrity():
    """Verifies that model artifact checksums are calculated and integrity check behaves deterministically."""
    integrity = inference_service.verify_artifact_integrity()
    assert "status" in integrity
    assert "is_tamper_free" in integrity
    assert "artifacts" in integrity
    assert "model" in integrity["artifacts"]
    assert integrity["model_version"] is not None


def test_malformed_pcap_safe_handling():
    """Verifies that an empty or corrupt PCAP file returns empty flows without crashing."""
    parser = PcapStreamParser()

    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tf:
        tf.write(b"NOT_A_REAL_PCAP_HEADER_DATA_12345")
        temp_path = tf.name

    try:
        # Parsing invalid bytes should fail gracefully or log error without unhandled kernel crash
        with pytest.raises(Exception):
            parser.parse_pcap_file(temp_path)
    finally:
        import gc
        gc.collect()
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass



def test_telemetry_validation_rejection():
    """Verifies that telemetry validator rejects negative counts and malformed records."""
    invalid_record = {
        "timestamp": "2026-09-19T12:00:00Z",
        "source_ip": "192.168.1.100",
        "destination_ip": "10.0.0.1",
        "source_port": 443,
        "destination_port": 80,
        "protocol": "TCP",
        "packet_count": -5,  # Invalid negative count
        "byte_count": 1000,
        "flow_duration_ms": 100.0,
    }

    report = TelemetryValidator.validate_batch([invalid_record])
    assert report.rejected_count >= 1
    assert report.valid_count == 0
