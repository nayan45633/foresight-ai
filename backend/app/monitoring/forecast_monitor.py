"""Foresight AI - Multi-Horizon Forecast Performance Monitor (Step 11).

Tracks empirical forecast accuracy metrics (Precision, Recall, F1, PR-AUC, Lead Time)
separately across all four discrete horizons (+5m, +15m, +30m, +60m) when ground truth is verified.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field


class PerformanceStatus(str, Enum):
    INSUFFICIENT_EMPIRICAL_EVIDENCE = "INSUFFICIENT_EMPIRICAL_EVIDENCE"
    OPTIMAL = "OPTIMAL"
    ACCEPTABLE = "ACCEPTABLE"
    DEGRADED = "DEGRADED"


class HorizonPerformanceMetric(BaseModel):
    horizon_minutes: int
    sample_count: int = 0
    attack_events_count: int = 0
    status: PerformanceStatus = PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    pr_auc: Optional[float] = None
    roc_auc: Optional[float] = None
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    mean_empirical_lead_time_minutes: Optional[float] = None
    min_empirical_lead_time_minutes: Optional[float] = None
    max_empirical_lead_time_minutes: Optional[float] = None
    interpretation: str = "INSUFFICIENT EMPIRICAL EVIDENCE: Requires at least 5 confirmed attack events."


class ForecastPerformanceReport(BaseModel):
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "production-v1"
    overall_status: PerformanceStatus = PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE
    has_sufficient_events: bool = False
    total_evaluated_samples: int = 0
    total_confirmed_attacks: int = 0
    per_horizon_performance: Dict[str, HorizonPerformanceMetric] = {}
    summary_message: str = "INSUFFICIENT EMPIRICAL EVIDENCE: Live operational period has not yet accumulated sufficient ground-truth attack incidents."


class ForecastPerformanceMonitor:
    """Evaluates multi-horizon classification and lead-time metrics with strict sample guards."""

    MIN_ATTACK_EVENTS = 5

    def evaluate_horizon(
        self,
        y_prob: np.ndarray,
        y_true: Optional[np.ndarray],
        decision_threshold: float = 0.5,
        horizon_minutes: int = 15,
        lead_times_minutes: Optional[List[float]] = None,
    ) -> HorizonPerformanceMetric:
        """Evaluates classification performance for a single forecast horizon."""
        if y_true is None or len(y_true) == 0 or y_prob is None or len(y_prob) == 0:
            return HorizonPerformanceMetric(
                horizon_minutes=horizon_minutes,
                status=PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE,
                interpretation="INSUFFICIENT EMPIRICAL EVIDENCE: No ground truth events available.",
            )

        y_t = np.asarray(y_true, dtype=int)
        y_p = np.asarray(y_prob, dtype=float)
        n = len(y_t)
        pos_count = int(np.sum(y_t == 1))

        if pos_count < self.MIN_ATTACK_EVENTS:
            return HorizonPerformanceMetric(
                horizon_minutes=horizon_minutes,
                sample_count=n,
                attack_events_count=pos_count,
                status=PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE,
                interpretation=f"INSUFFICIENT EMPIRICAL EVIDENCE: {pos_count} confirmed events (minimum {self.MIN_ATTACK_EVENTS} required).",
            )

        y_pred = (y_p >= decision_threshold).astype(int)
        tp = int(np.sum((y_pred == 1) & (y_t == 1)))
        fp = int(np.sum((y_pred == 1) & (y_t == 0)))
        tn = int(np.sum((y_pred == 0) & (y_t == 0)))
        fn = int(np.sum((y_pred == 0) & (y_t == 1)))

        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        mean_lead, min_lead, max_lead = None, None, None
        if lead_times_minutes and len(lead_times_minutes) > 0:
            mean_lead = float(np.mean(lead_times_minutes))
            min_lead = float(np.min(lead_times_minutes))
            max_lead = float(np.max(lead_times_minutes))

        if f1 >= 0.85:
            status = PerformanceStatus.OPTIMAL
            interp = f"Optimal forecast performance: F1={f1:.3f}, Precision={precision:.3f}, Recall={recall:.3f}."
        elif f1 >= 0.70:
            status = PerformanceStatus.ACCEPTABLE
            interp = f"Acceptable forecast performance: F1={f1:.3f}, Precision={precision:.3f}, Recall={recall:.3f}."
        else:
            status = PerformanceStatus.DEGRADED
            interp = f"Degraded forecast performance: F1={f1:.3f} below operational threshold."

        return HorizonPerformanceMetric(
            horizon_minutes=horizon_minutes,
            sample_count=n,
            attack_events_count=pos_count,
            status=status,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            mean_empirical_lead_time_minutes=round(mean_lead, 2) if mean_lead is not None else None,
            min_empirical_lead_time_minutes=round(min_lead, 2) if min_lead is not None else None,
            max_empirical_lead_time_minutes=round(max_lead, 2) if max_lead is not None else None,
            interpretation=interp,
        )

    def evaluate_all_horizons(
        self,
        horizon_preds: Dict[int, np.ndarray],
        horizon_gt: Optional[Dict[int, np.ndarray]],
        model_version: str = "production-v1",
    ) -> ForecastPerformanceReport:
        """Evaluates metrics across all horizons without inter-horizon contamination."""
        has_sufficient = (
            horizon_gt is not None
            and any(v is not None and np.sum(np.asarray(v) == 1) >= self.MIN_ATTACK_EVENTS for v in horizon_gt.values())
        )

        if not has_sufficient:
            return ForecastPerformanceReport(
                model_version=model_version,
                overall_status=PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE,
                has_sufficient_events=False,
                per_horizon_performance={
                    str(h): HorizonPerformanceMetric(horizon_minutes=h)
                    for h in [5, 15, 30, 60]
                },
                summary_message="INSUFFICIENT EMPIRICAL EVIDENCE: Awaiting sufficient recorded attack incident ground truth.",
            )

        h_map: Dict[str, HorizonPerformanceMetric] = {}
        statuses = []
        tot_samples = 0
        tot_attacks = 0

        for h in [5, 15, 30, 60]:
            p = horizon_preds.get(h, np.array([]))
            gt = horizon_gt.get(h) if horizon_gt else None
            metric = self.evaluate_horizon(p, gt, horizon_minutes=h)
            h_map[str(h)] = metric
            statuses.append(metric.status)
            tot_samples += metric.sample_count
            tot_attacks += metric.attack_events_count

        if PerformanceStatus.DEGRADED in statuses:
            overall = PerformanceStatus.DEGRADED
            msg = "Degraded forecast accuracy observed on one or more horizons."
        elif PerformanceStatus.ACCEPTABLE in statuses:
            overall = PerformanceStatus.ACCEPTABLE
            msg = "Multi-horizon forecasting accuracy is within acceptable operational tolerance."
        elif PerformanceStatus.OPTIMAL in statuses:
            overall = PerformanceStatus.OPTIMAL
            msg = "High multi-horizon forecasting precision and recall across evaluated horizons."
        else:
            overall = PerformanceStatus.INSUFFICIENT_EMPIRICAL_EVIDENCE
            msg = "Insufficient empirical ground truth across horizons."

        return ForecastPerformanceReport(
            model_version=model_version,
            overall_status=overall,
            has_sufficient_events=True,
            total_evaluated_samples=tot_samples,
            total_confirmed_attacks=tot_attacks,
            per_horizon_performance=h_map,
            summary_message=msg,
        )
