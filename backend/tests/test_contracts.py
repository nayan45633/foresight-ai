"""Foresight AI - Test ML & Telemetry Data Contracts & Feature Pipeline."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.ml.contracts import (
    FlowDirectionEnum,
    FlowRecord,
    ForecastHorizonPrediction,
    ForecastResult,
    ProtocolEnum,
    ThreatSeverityEnum,
    UncertaintyEstimate,
)
from app.ml.pipeline import StatisticalFeatureExtractor, StandardTelemetryNormalizer


def test_flow_record_contract_validation():
    valid_flow = FlowRecord(
        timestamp=datetime.now(timezone.utc),
        source_ip="192.168.1.100",
        destination_ip="10.0.0.5",
        source_port=54321,
        destination_port=443,
        protocol=ProtocolEnum.TCP,
        flow_duration_ms=125.5,
        packet_count=12,
        byte_count=4500,
        tcp_flags="SYN,ACK",
        direction=FlowDirectionEnum.INGRESS,
    )
    assert valid_flow.protocol == ProtocolEnum.TCP
    assert valid_flow.source_port == 54321

    # Port out of bounds should fail
    with pytest.raises(ValidationError):
        FlowRecord(
            source_ip="192.168.1.1",
            destination_ip="192.168.1.2",
            source_port=70000,  # Invalid
            destination_port=80,
        )


def test_forecast_result_contract():
    result = ForecastResult(
        id="fc-test-001",
        forecast=ForecastHorizonPrediction(
            threat="Distributed Denial of Service",
            probability=0.87,
            confidence=0.92,
            horizon_minutes=15,
            severity=ThreatSeverityEnum.HIGH,
        ),
        anomaly_score=0.74,
        uncertainty=UncertaintyEstimate(
            credible_interval_lower=0.81,
            credible_interval_upper=0.93,
            confidence_level=0.95,
        ),
        model_version="v1.0.0-test",
    )
    assert result.forecast.threat == "Distributed Denial of Service"
    assert result.forecast.horizon_minutes == 15
    assert result.uncertainty.credible_interval_lower == 0.81


def test_telemetry_normalizer_and_feature_extractor():
    normalizer = StandardTelemetryNormalizer()
    extractor = StatisticalFeatureExtractor()

    raw_flows = [
        {
            "src_ip": "10.0.0.10",
            "dst_ip": "10.0.0.1",
            "src_port": 1000 + i,
            "dst_port": 80,
            "proto": "TCP",
            "duration_ms": 50.0,
            "packets": 10,
            "bytes": 5000,
            "flags": "SYN",
        }
        for i in range(5)
    ]

    normalized = normalizer.batch_normalize(raw_flows)
    assert len(normalized) == 5
    assert normalized[0].protocol == ProtocolEnum.TCP

    features = extractor.extract_window_features(normalized, window_duration_seconds=60)
    assert features.flow_volume == 5
    assert features.packet_volume == 50
    assert features.byte_volume == 25000
    assert features.syn_ack_ratio == 1.0
    assert len(features.vector) == 10
