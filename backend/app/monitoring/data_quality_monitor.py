"""Foresight AI - Statistical Data Quality Monitor.

Monitors raw and feature-engineered telemetry streams for missing values, range violations,
NaN/Infinity anomalies, duplicate flow rates, and protocol distribution consistency.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field


class MonitoringStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class FeatureQualityMetric(BaseModel):
    feature_name: str
    feature_index: int
    missing_count: int = 0
    missing_rate: float = 0.0
    nan_count: int = 0
    inf_count: int = 0
    min_observed: float = 0.0
    max_observed: float = 0.0
    mean_observed: float = 0.0
    std_observed: float = 0.0
    range_violations: int = 0
    status: MonitoringStatus = MonitoringStatus.HEALTHY


class DataQualityReport(BaseModel):
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sample_count: int = 0
    total_features_monitored: int = 37
    schema_version: str = "v1.0.0"
    overall_status: MonitoringStatus = MonitoringStatus.HEALTHY
    completeness_score: float = 1.0
    validity_score: float = 1.0
    duplicate_rate: float = 0.0
    feature_metrics: List[FeatureQualityMetric] = []
    anomalies_detected: List[str] = []
    summary_message: str = "Telemetry data quality is within normal operating limits."


class DataQualityMonitor:
    """Evaluates empirical data quality across window feature matrices."""

    def __init__(self, expected_feature_count: int = 37):
        self.expected_feature_count = expected_feature_count

    def evaluate_batch(
        self,
        feature_matrix: np.ndarray,
        feature_names: Optional[List[str]] = None,
        duplicate_rate: float = 0.0,
    ) -> DataQualityReport:
        """Evaluates numerical data quality over an observation matrix (N, 37)."""
        if feature_matrix is None or len(feature_matrix) == 0:
            return DataQualityReport(
                sample_count=0,
                overall_status=MonitoringStatus.WATCH,
                completeness_score=0.0,
                validity_score=0.0,
                summary_message="No feature vectors provided in evaluation window (INSUFFICIENT DATA).",
            )

        if not isinstance(feature_matrix, np.ndarray):
            feature_matrix = np.array(feature_matrix, dtype=np.float32)

        if feature_matrix.ndim == 1:
            feature_matrix = feature_matrix.reshape(1, -1)

        num_samples, num_cols = feature_matrix.shape
        names = feature_names or [f"feature_{i}" for i in range(num_cols)]

        if num_cols != self.expected_feature_count:
            return DataQualityReport(
                sample_count=num_samples,
                total_features_monitored=num_cols,
                overall_status=MonitoringStatus.CRITICAL,
                completeness_score=0.0,
                validity_score=0.0,
                anomalies_detected=[
                    f"Schema dimension mismatch: Expected {self.expected_feature_count} features, received {num_cols}"
                ],
                summary_message=f"Critical schema mismatch: {num_cols} != {self.expected_feature_count}",
            )

        metrics: List[FeatureQualityMetric] = []
        total_nans = 0
        total_infs = 0
        total_violations = 0
        anomalies: List[str] = []

        for idx in range(num_cols):
            col = feature_matrix[:, idx]
            name = names[idx] if idx < len(names) else f"feature_{idx}"

            nan_mask = np.isnan(col)
            inf_mask = np.isinf(col)
            nan_cnt = int(np.sum(nan_mask))
            inf_cnt = int(np.sum(inf_mask))
            total_nans += nan_cnt
            total_infs += inf_cnt

            valid_vals = col[~(nan_mask | inf_mask)]
            if len(valid_vals) > 0:
                min_v = float(np.min(valid_vals))
                max_v = float(np.max(valid_vals))
                mean_v = float(np.mean(valid_vals))
                std_v = float(np.std(valid_vals))
            else:
                min_v, max_v, mean_v, std_v = 0.0, 0.0, 0.0, 0.0

            # Range violation checks: rates or counts shouldn't be negative
            neg_count = int(np.sum(valid_vals < -1e-5)) if "ratio" not in name and "delta" not in name and "shap" not in name else 0
            total_violations += neg_count

            # Feature status
            if nan_cnt > 0 or inf_cnt > 0 or neg_count > 0:
                f_status = MonitoringStatus.DEGRADED if (nan_cnt + inf_cnt) > (0.05 * num_samples) else MonitoringStatus.WATCH
                anomalies.append(f"{name}: {nan_cnt} NaNs, {inf_cnt} Infs, {neg_count} negative violations")
            else:
                f_status = MonitoringStatus.HEALTHY

            metrics.append(
                FeatureQualityMetric(
                    feature_name=name,
                    feature_index=idx,
                    missing_count=nan_cnt,
                    missing_rate=round(nan_cnt / max(1, num_samples), 4),
                    nan_count=nan_cnt,
                    inf_count=inf_cnt,
                    min_observed=round(min_v, 4),
                    max_observed=round(max_v, 4),
                    mean_observed=round(mean_v, 4),
                    std_observed=round(std_v, 4),
                    range_violations=neg_count,
                    status=f_status,
                )
            )

        total_values = num_samples * num_cols
        completeness = 1.0 - (total_nans / max(1, total_values))
        validity = 1.0 - ((total_nans + total_infs + total_violations) / max(1, total_values))

        # Overall status determination
        if total_nans > (0.10 * total_values) or total_infs > 0:
            overall = MonitoringStatus.CRITICAL
            msg = f"Critical telemetry quality issues: {total_nans} NaNs, {total_infs} Infs across {num_samples} samples."
        elif validity < 0.95 or duplicate_rate > 0.05:
            overall = MonitoringStatus.DEGRADED
            msg = f"Degraded data quality: validity={validity:.2%}, duplicate_rate={duplicate_rate:.2%}."
        elif validity < 0.99 or duplicate_rate > 0.01:
            overall = MonitoringStatus.WATCH
            msg = f"Minor data quality anomalies observed: validity={validity:.2%}."
        else:
            overall = MonitoringStatus.HEALTHY
            msg = f"Data quality healthy across {num_samples} observation vectors ({validity:.2%} valid)."

        return DataQualityReport(
            sample_count=num_samples,
            total_features_monitored=num_cols,
            schema_version="v1.0.0",
            overall_status=overall,
            completeness_score=round(completeness, 4),
            validity_score=round(validity, 4),
            duplicate_rate=round(duplicate_rate, 4),
            feature_metrics=metrics,
            anomalies_detected=anomalies[:10],
            summary_message=msg,
        )
