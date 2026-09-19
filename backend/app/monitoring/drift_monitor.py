"""Foresight AI - Statistical Drift Monitor (Step 11).

Calculates Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) two-sample statistics
to monitor feature drift and prediction distribution shift against baseline distributions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field


class DriftStatus(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STABLE = "STABLE"
    MODERATE_DRIFT = "MODERATE_DRIFT"
    SIGNIFICANT_DRIFT = "SIGNIFICANT_DRIFT"


class FeatureDriftMetric(BaseModel):
    feature_name: str
    feature_index: int
    psi_score: Optional[float] = None
    ks_statistic: Optional[float] = None
    baseline_mean: float = 0.0
    current_mean: float = 0.0
    baseline_std: float = 0.0
    current_std: float = 0.0
    status: DriftStatus = DriftStatus.INSUFFICIENT_DATA
    interpretation: str = ""


class PredictionDriftSummary(BaseModel):
    sample_count: int = 0
    positive_rate_baseline: float = 0.0
    positive_rate_current: float = 0.0
    rate_shift_delta: float = 0.0
    mean_predicted_probability: float = 0.0
    percentiles: Dict[str, float] = {}
    status: DriftStatus = DriftStatus.INSUFFICIENT_DATA
    interpretation: str = "INSUFFICIENT_DATA: Observation window requires at least 30 predictions."


class DriftReport(BaseModel):
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_sample_count: int = 0
    current_sample_count: int = 0
    min_required_samples: int = 30
    overall_drift_status: DriftStatus = DriftStatus.INSUFFICIENT_DATA
    drifted_features_count: int = 0
    total_features_monitored: int = 37
    feature_drift_metrics: List[FeatureDriftMetric] = []
    prediction_drift: Dict[str, PredictionDriftSummary] = {}
    summary_message: str = "INSUFFICIENT_DATA: Awaiting minimum telemetry observation samples."


class DriftMonitor:
    """Computes empirical drift metrics with conservative sample size guards."""

    PSI_THRESHOLD_MODERATE = 0.10
    PSI_THRESHOLD_SIGNIFICANT = 0.25
    MIN_SAMPLE_SIZE = 30

    @staticmethod
    def compute_psi(
        baseline: np.ndarray,
        current: np.ndarray,
        num_bins: int = 10,
        epsilon: float = 1e-4,
    ) -> float:
        """Calculates Population Stability Index (PSI) between baseline and current distributions."""
        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        # Compute quantile bin edges from baseline
        quantiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        # Make bin edges strictly monotonic
        for i in range(1, len(bin_edges)):
            if bin_edges[i] <= bin_edges[i - 1]:
                bin_edges[i] = bin_edges[i - 1] + 1e-6

        # Bin counts
        b_counts, _ = np.histogram(baseline, bins=bin_edges)
        c_counts, _ = np.histogram(current, bins=bin_edges)

        # Proportions with Laplace/epsilon smoothing
        p_b = (b_counts + epsilon) / (np.sum(b_counts) + epsilon * num_bins)
        p_c = (c_counts + epsilon) / (np.sum(c_counts) + epsilon * num_bins)

        # PSI formula
        psi_value = np.sum((p_c - p_b) * np.log(p_c / p_b))
        return float(max(0.0, psi_value))

    @staticmethod
    def compute_ks_statistic(baseline: np.ndarray, current: np.ndarray) -> float:
        """Computes Kolmogorov-Smirnov 2-sample max empirical CDF discrepancy."""
        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        all_vals = np.sort(np.unique(np.concatenate([baseline, current])))
        cdf_b = np.searchsorted(np.sort(baseline), all_vals, side="right") / len(baseline)
        cdf_c = np.searchsorted(np.sort(current), all_vals, side="right") / len(current)

        return float(np.max(np.abs(cdf_b - cdf_c)))

    def evaluate_feature_drift(
        self,
        baseline_matrix: np.ndarray,
        current_matrix: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> DriftReport:
        """Evaluates drift for each feature between baseline and current matrix partitions."""
        n_base = len(baseline_matrix) if baseline_matrix is not None else 0
        n_curr = len(current_matrix) if current_matrix is not None else 0

        if n_base < self.MIN_SAMPLE_SIZE or n_curr < self.MIN_SAMPLE_SIZE:
            return DriftReport(
                baseline_sample_count=n_base,
                current_sample_count=n_curr,
                min_required_samples=self.MIN_SAMPLE_SIZE,
                overall_drift_status=DriftStatus.INSUFFICIENT_DATA,
                summary_message=(
                    f"INSUFFICIENT_DATA: Observation window has {n_curr} samples "
                    f"(baseline {n_base}), minimum required is {self.MIN_SAMPLE_SIZE}."
                ),
            )

        num_cols = baseline_matrix.shape[1]
        names = feature_names or [f"feature_{i}" for i in range(num_cols)]

        feature_metrics: List[FeatureDriftMetric] = []
        drifted_count = 0
        moderate_count = 0

        for idx in range(num_cols):
            b_col = np.nan_to_num(baseline_matrix[:, idx], nan=0.0)
            c_col = np.nan_to_num(current_matrix[:, idx], nan=0.0)
            name = names[idx] if idx < len(names) else f"feature_{idx}"

            psi = self.compute_psi(b_col, c_col)
            ks = self.compute_ks_statistic(b_col, c_col)

            b_mean, c_mean = float(np.mean(b_col)), float(np.mean(c_col))
            b_std, c_std = float(np.std(b_col)), float(np.std(c_col))

            if psi >= self.PSI_THRESHOLD_SIGNIFICANT:
                status = DriftStatus.SIGNIFICANT_DRIFT
                interp = f"Significant distributional drift detected (PSI={psi:.3f} >= {self.PSI_THRESHOLD_SIGNIFICANT})."
                drifted_count += 1
            elif psi >= self.PSI_THRESHOLD_MODERATE:
                status = DriftStatus.MODERATE_DRIFT
                interp = f"Moderate distribution drift observed (PSI={psi:.3f})."
                moderate_count += 1
            else:
                status = DriftStatus.STABLE
                interp = f"Distribution is stable (PSI={psi:.3f})."

            feature_metrics.append(
                FeatureDriftMetric(
                    feature_name=name,
                    feature_index=idx,
                    psi_score=round(psi, 4),
                    ks_statistic=round(ks, 4),
                    baseline_mean=round(b_mean, 4),
                    current_mean=round(c_mean, 4),
                    baseline_std=round(b_std, 4),
                    current_std=round(c_std, 4),
                    status=status,
                    interpretation=interp,
                )
            )

        if drifted_count >= 3:
            overall = DriftStatus.SIGNIFICANT_DRIFT
            msg = f"Significant feature drift detected across {drifted_count} features."
        elif moderate_count >= 5 or drifted_count > 0:
            overall = DriftStatus.MODERATE_DRIFT
            msg = f"Moderate feature drift detected across {moderate_count} features."
        else:
            overall = DriftStatus.STABLE
            msg = f"All {num_cols} monitored features are within statistical stability thresholds."

        return DriftReport(
            baseline_sample_count=n_base,
            current_sample_count=n_curr,
            min_required_samples=self.MIN_SAMPLE_SIZE,
            overall_drift_status=overall,
            drifted_features_count=drifted_count,
            total_features_monitored=num_cols,
            feature_drift_metrics=feature_metrics,
            summary_message=msg,
        )

    def evaluate_prediction_drift(
        self,
        baseline_probs: np.ndarray,
        current_probs: np.ndarray,
        threshold: float = 0.5,
    ) -> PredictionDriftSummary:
        """Evaluates prediction distribution shift across forecast probabilities."""
        n_curr = len(current_probs) if current_probs is not None else 0
        if n_curr < self.MIN_SAMPLE_SIZE or baseline_probs is None or len(baseline_probs) < self.MIN_SAMPLE_SIZE:
            return PredictionDriftSummary(
                sample_count=n_curr,
                status=DriftStatus.INSUFFICIENT_DATA,
                interpretation=f"INSUFFICIENT_DATA: Observation window has {n_curr} samples, minimum {self.MIN_SAMPLE_SIZE} required.",
            )

        b_rate = float(np.mean(baseline_probs >= threshold))
        c_rate = float(np.mean(current_probs >= threshold))
        delta = c_rate - b_rate
        mean_p = float(np.mean(current_probs))

        percentiles = {
            "p10": round(float(np.percentile(current_probs, 10)), 4),
            "p50": round(float(np.percentile(current_probs, 50)), 4),
            "p90": round(float(np.percentile(current_probs, 90)), 4),
        }

        if abs(delta) > 0.20:
            status = DriftStatus.SIGNIFICANT_DRIFT
            interp = f"Significant prediction distribution shift: positive rate changed by {delta:+.2%}."
        elif abs(delta) > 0.08:
            status = DriftStatus.MODERATE_DRIFT
            interp = f"Moderate prediction distribution shift: positive rate changed by {delta:+.2%}."
        else:
            status = DriftStatus.STABLE
            interp = f"Prediction distribution stable (mean={mean_p:.2f}, positive rate={c_rate:.2%})."

        return PredictionDriftSummary(
            sample_count=n_curr,
            positive_rate_baseline=round(b_rate, 4),
            positive_rate_current=round(c_rate, 4),
            rate_shift_delta=round(delta, 4),
            mean_predicted_probability=round(mean_p, 4),
            percentiles=percentiles,
            status=status,
            interpretation=interp,
        )
