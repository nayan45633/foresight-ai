"""Foresight AI - Calibration & Conformal Reliability Monitor (Step 11).

Evaluates Brier scores, Expected Calibration Error (ECE), and empirical marginal coverage
of conformal prediction sets against verified ground-truth labels.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field


class CalibrationHealthStatus(str, Enum):
    AWAITING_GROUND_TRUTH = "AWAITING_GROUND_TRUTH"
    CALIBRATED = "CALIBRATED"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"


class ReliabilityBinMetric(BaseModel):
    bin_index: int
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_confidence: float
    observed_frequency: float
    calibration_error: float


class HorizonCalibrationHealth(BaseModel):
    horizon_minutes: int
    sample_count: int = 0
    status: CalibrationHealthStatus = CalibrationHealthStatus.AWAITING_GROUND_TRUTH
    brier_score: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    maximum_calibration_error: Optional[float] = None
    conformal_target_coverage: float = 0.90
    conformal_empirical_coverage: Optional[float] = None
    conformal_coverage_gap: Optional[float] = None
    reliability_bins: List[ReliabilityBinMetric] = []
    interpretation: str = "AWAITING GROUND TRUTH: Verified event labels required for calibration evaluation."


class CalibrationHealthReport(BaseModel):
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "production-v1"
    overall_status: CalibrationHealthStatus = CalibrationHealthStatus.AWAITING_GROUND_TRUTH
    has_ground_truth: bool = False
    samples_evaluated: int = 0
    per_horizon_calibration: Dict[str, HorizonCalibrationHealth] = {}
    summary_message: str = "AWAITING GROUND TRUTH: Calibration monitoring requires recorded post-event labels."


class CalibrationMonitor:
    """Evaluates probability calibration and conformal coverage when ground truth labels are available."""

    def __init__(self, num_bins: int = 10, target_coverage: float = 0.90):
        self.num_bins = num_bins
        self.target_coverage = target_coverage

    def evaluate_calibration(
        self,
        predicted_probabilities: np.ndarray,
        ground_truth_labels: Optional[np.ndarray],
        conformal_sets: Optional[List[List[int]]] = None,
        horizon_minutes: int = 15,
        model_version: str = "production-v1",
    ) -> HorizonCalibrationHealth:
        """Calculates Brier score, ECE, and empirical conformal coverage for a single horizon."""
        if ground_truth_labels is None or len(ground_truth_labels) == 0:
            return HorizonCalibrationHealth(
                horizon_minutes=horizon_minutes,
                sample_count=len(predicted_probabilities) if predicted_probabilities is not None else 0,
                status=CalibrationHealthStatus.AWAITING_GROUND_TRUTH,
                conformal_target_coverage=self.target_coverage,
                interpretation="AWAITING GROUND TRUTH: Verified labels not yet available in current time window.",
            )

        y_true = np.asarray(ground_truth_labels, dtype=int)
        y_prob = np.asarray(predicted_probabilities, dtype=float)
        n = len(y_true)

        if n == 0 or len(y_prob) != n:
            return HorizonCalibrationHealth(
                horizon_minutes=horizon_minutes,
                sample_count=n,
                status=CalibrationHealthStatus.AWAITING_GROUND_TRUTH,
                conformal_target_coverage=self.target_coverage,
                interpretation="AWAITING GROUND TRUTH: Empty or dimension-mismatched ground truth array.",
            )

        # 1. Brier Score: Mean squared error of probabilities
        brier = float(np.mean((y_prob - y_true) ** 2))

        # 2. Reliability Diagram & ECE
        bins = np.linspace(0.0, 1.0, self.num_bins + 1)
        bin_metrics: List[ReliabilityBinMetric] = []
        weighted_ece = 0.0
        max_cal_error = 0.0

        for i in range(self.num_bins):
            b_low = bins[i]
            b_high = bins[i + 1]
            if i == self.num_bins - 1:
                mask = (y_prob >= b_low) & (y_prob <= b_high)
            else:
                mask = (y_prob >= b_low) & (y_prob < b_high)

            count = int(np.sum(mask))
            if count > 0:
                mean_conf = float(np.mean(y_prob[mask]))
                obs_freq = float(np.mean(y_true[mask]))
                cal_err = abs(obs_freq - mean_conf)
                weighted_ece += (count / n) * cal_err
                max_cal_error = max(max_cal_error, cal_err)
            else:
                mean_conf = (b_low + b_high) / 2.0
                obs_freq = 0.0
                cal_err = 0.0

            bin_metrics.append(
                ReliabilityBinMetric(
                    bin_index=i,
                    bin_lower=round(b_low, 2),
                    bin_upper=round(b_high, 2),
                    sample_count=count,
                    mean_confidence=round(mean_conf, 4),
                    observed_frequency=round(obs_freq, 4),
                    calibration_error=round(cal_err, 4),
                )
            )

        # 3. Conformal Coverage
        emp_coverage = None
        cov_gap = None
        if conformal_sets and len(conformal_sets) == n:
            covered = sum(1 for label, c_set in zip(y_true, conformal_sets) if label in c_set)
            emp_coverage = float(covered / n)
            cov_gap = float(emp_coverage - self.target_coverage)

        # 4. Status determination
        if weighted_ece > 0.15 or (emp_coverage is not None and emp_coverage < self.target_coverage - 0.10):
            status = CalibrationHealthStatus.DEGRADED
            interp = f"Degraded calibration: ECE={weighted_ece:.3f}, Brier={brier:.3f}."
        elif weighted_ece > 0.08 or (emp_coverage is not None and emp_coverage < self.target_coverage - 0.04):
            status = CalibrationHealthStatus.WATCH
            interp = f"Minor calibration drift: ECE={weighted_ece:.3f}, Brier={brier:.3f}."
        else:
            status = CalibrationHealthStatus.CALIBRATED
            interp = f"Well-calibrated: ECE={weighted_ece:.3f}, Brier={brier:.3f}."

        return HorizonCalibrationHealth(
            horizon_minutes=horizon_minutes,
            sample_count=n,
            status=status,
            brier_score=round(brier, 4),
            expected_calibration_error=round(weighted_ece, 4),
            maximum_calibration_error=round(max_cal_error, 4),
            conformal_target_coverage=self.target_coverage,
            conformal_empirical_coverage=round(emp_coverage, 4) if emp_coverage is not None else None,
            conformal_coverage_gap=round(cov_gap, 4) if cov_gap is not None else None,
            reliability_bins=bin_metrics,
            interpretation=interp,
        )

    def evaluate_all_horizons(
        self,
        horizon_predictions: Dict[int, np.ndarray],
        ground_truth: Optional[Dict[int, np.ndarray]],
        model_version: str = "production-v1",
    ) -> CalibrationHealthReport:
        """Evaluates calibration report across all four horizons (+5m, +15m, +30m, +60m)."""
        has_gt = ground_truth is not None and any(v is not None and len(v) > 0 for v in ground_truth.values())
        if not has_gt:
            return CalibrationHealthReport(
                model_version=model_version,
                overall_status=CalibrationHealthStatus.AWAITING_GROUND_TRUTH,
                has_ground_truth=False,
                samples_evaluated=0,
                per_horizon_calibration={
                    str(h): HorizonCalibrationHealth(horizon_minutes=h)
                    for h in [5, 15, 30, 60]
                },
                summary_message="AWAITING GROUND TRUTH: Calibration metrics cannot be computed without verified attack event labels.",
            )

        h_reports: Dict[str, HorizonCalibrationHealth] = {}
        statuses = []

        for h in [5, 15, 30, 60]:
            preds = horizon_predictions.get(h, np.array([]))
            gt = ground_truth.get(h) if ground_truth else None
            h_rep = self.evaluate_calibration(preds, gt, horizon_minutes=h, model_version=model_version)
            h_reports[str(h)] = h_rep
            statuses.append(h_rep.status)

        if CalibrationHealthStatus.DEGRADED in statuses:
            overall = CalibrationHealthStatus.DEGRADED
            msg = "Degraded calibration observed on one or more forecast horizons."
        elif CalibrationHealthStatus.WATCH in statuses:
            overall = CalibrationHealthStatus.WATCH
            msg = "Minor calibration deviations detected on evaluated forecast horizons."
        else:
            overall = CalibrationHealthStatus.CALIBRATED
            msg = "All evaluated forecast horizons demonstrate strong probability calibration."

        return CalibrationHealthReport(
            model_version=model_version,
            overall_status=overall,
            has_ground_truth=True,
            samples_evaluated=sum(r.sample_count for r in h_reports.values()),
            per_horizon_calibration=h_reports,
            summary_message=msg,
        )
