"""Foresight AI - Composite Model Health & Integrity Evaluator (Step 11).

Evaluates the global operational health of the forecasting subsystem by fusing
artifact integrity, data quality, statistical drift, calibration stability, and inference latency.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.monitoring.data_quality_monitor import MonitoringStatus


class CompositeHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class HealthSignal(BaseModel):
    category: str
    status: CompositeHealthStatus
    details: str
    is_blocking: bool = False


class CompositeModelHealthReport(BaseModel):
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "production-v1"
    feature_schema_version: str = "v1.0.0"
    calibration_version: str = "v1.0.0"
    conformal_version: str = "v1.0.0"
    overall_status: CompositeHealthStatus = CompositeHealthStatus.HEALTHY
    artifact_integrity_verified: bool = True
    artifact_checksums_match: bool = True
    inference_p50_latency_ms: float = 0.0
    inference_p95_latency_ms: float = 0.0
    recent_error_rate: float = 0.0
    signals: List[HealthSignal] = []
    summary_message: str = "Model health is verified and operational."


class ModelHealthEvaluator:
    """Combines observability signals into a rigorous, explainable composite health state."""

    @staticmethod
    def evaluate(
        model_version: str,
        artifact_integrity: Dict[str, Any],
        data_quality_status: MonitoringStatus,
        drift_status: str,
        calibration_status: str,
        performance_status: str,
        p50_latency_ms: float = 12.5,
        p95_latency_ms: float = 28.0,
        recent_error_rate: float = 0.0,
    ) -> CompositeModelHealthReport:
        """Determines the composite health status deterministically from underlying signals."""
        signals: List[HealthSignal] = []
        is_tamper_free = artifact_integrity.get("is_tamper_free", True)

        # 1. Artifact Integrity Signal
        if not is_tamper_free or artifact_integrity.get("status") != "VERIFIED":
            signals.append(
                HealthSignal(
                    category="Artifact Integrity",
                    status=CompositeHealthStatus.CRITICAL,
                    details="One or more model artifact checksums could not be verified or were tampered with.",
                    is_blocking=True,
                )
            )
        else:
            signals.append(
                HealthSignal(
                    category="Artifact Integrity",
                    status=CompositeHealthStatus.HEALTHY,
                    details="All 4 core model artifacts verified against SHA-256 checksums.",
                )
            )

        # 2. Data Quality Signal
        if data_quality_status == MonitoringStatus.CRITICAL:
            signals.append(
                HealthSignal(
                    category="Data Quality",
                    status=CompositeHealthStatus.CRITICAL,
                    details="Critical data quality degradation: severe NaN/Inf rates or schema mismatch.",
                    is_blocking=True,
                )
            )
        elif data_quality_status == MonitoringStatus.DEGRADED:
            signals.append(
                HealthSignal(
                    category="Data Quality",
                    status=CompositeHealthStatus.DEGRADED,
                    details="Degraded telemetry quality: high missing rates or range violations.",
                )
            )
        elif data_quality_status == MonitoringStatus.WATCH:
            signals.append(
                HealthSignal(
                    category="Data Quality",
                    status=CompositeHealthStatus.WATCH,
                    details="Minor data quality anomalies observed in observation window.",
                )
            )
        else:
            signals.append(
                HealthSignal(
                    category="Data Quality",
                    status=CompositeHealthStatus.HEALTHY,
                    details="Input data streams satisfy authoritative 37-feature schema specifications.",
                )
            )

        # 3. Statistical Drift Signal
        if drift_status == "SIGNIFICANT_DRIFT":
            signals.append(
                HealthSignal(
                    category="Statistical Drift",
                    status=CompositeHealthStatus.DEGRADED,
                    details="Significant feature distribution drift detected (PSI >= 0.25).",
                )
            )
        elif drift_status == "MODERATE_DRIFT":
            signals.append(
                HealthSignal(
                    category="Statistical Drift",
                    status=CompositeHealthStatus.WATCH,
                    details="Moderate feature distribution drift observed (0.10 <= PSI < 0.25).",
                )
            )
        else:
            signals.append(
                HealthSignal(
                    category="Statistical Drift",
                    status=CompositeHealthStatus.HEALTHY,
                    details="Feature distributions align with baseline calibration reference.",
                )
            )

        # 4. Calibration Stability Signal
        if calibration_status == "DEGRADED":
            signals.append(
                HealthSignal(
                    category="Probability Calibration",
                    status=CompositeHealthStatus.DEGRADED,
                    details="Observed probability calibration error (ECE > 0.15) exceeds operational threshold.",
                )
            )
        elif calibration_status == "WATCH":
            signals.append(
                HealthSignal(
                    category="Probability Calibration",
                    status=CompositeHealthStatus.WATCH,
                    details="Minor calibration drift noted against ground truth.",
                )
            )
        else:
            signals.append(
                HealthSignal(
                    category="Probability Calibration",
                    status=CompositeHealthStatus.HEALTHY,
                    details="Probability estimates maintain statistical calibration.",
                )
            )

        # 5. Latency & Reliability
        if p95_latency_ms > 500.0 or recent_error_rate > 0.05:
            signals.append(
                HealthSignal(
                    category="Inference Performance",
                    status=CompositeHealthStatus.DEGRADED,
                    details=f"Inference latency elevated (p95={p95_latency_ms:.1f}ms) or error rate={recent_error_rate:.1%}.",
                )
            )
        else:
            signals.append(
                HealthSignal(
                    category="Inference Performance",
                    status=CompositeHealthStatus.HEALTHY,
                    details=f"Inference latency optimal (p50={p50_latency_ms:.1f}ms, p95={p95_latency_ms:.1f}ms).",
                )
            )

        # Determine overall status
        blocking = [s for s in signals if s.status == CompositeHealthStatus.CRITICAL]
        degraded = [s for s in signals if s.status == CompositeHealthStatus.DEGRADED]
        watch = [s for s in signals if s.status == CompositeHealthStatus.WATCH]

        if blocking:
            overall = CompositeHealthStatus.CRITICAL
            msg = f"CRITICAL: Model subsystem requires immediate attention ({blocking[0].details})."
        elif degraded:
            overall = CompositeHealthStatus.DEGRADED
            msg = f"DEGRADED: Model reliability compromised ({degraded[0].details})."
        elif watch:
            overall = CompositeHealthStatus.WATCH
            msg = f"WATCH: Minor monitoring warnings active ({watch[0].details})."
        else:
            overall = CompositeHealthStatus.HEALTHY
            msg = "All model monitoring and integrity signals are HEALTHY."

        return CompositeModelHealthReport(
            model_version=model_version,
            feature_schema_version="v1.0.0",
            calibration_version="v1.0.0",
            conformal_version="v1.0.0",
            overall_status=overall,
            artifact_integrity_verified=is_tamper_free,
            artifact_checksums_match=is_tamper_free,
            inference_p50_latency_ms=round(p50_latency_ms, 2),
            inference_p95_latency_ms=round(p95_latency_ms, 2),
            recent_error_rate=round(recent_error_rate, 4),
            signals=signals,
            summary_message=msg,
        )
