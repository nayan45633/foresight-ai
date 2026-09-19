"""Foresight AI - Future Label Alignment & Forecasting Target Scaffolding.

Aligns historical sliding windows with future ground-truth attack labels at horizons:
- 5 minutes
- 15 minutes
- 30 minutes
- 60 minutes
Ensures zero temporal leakage between past feature vectors and forward targets.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.ml.contracts import FutureHorizonTarget, TemporalWindowFeatures


class FutureLabelAligner:
    """Constructs multi-horizon forecasting targets paired with temporal window features."""

    HORIZONS_MINUTES = [5, 15, 30, 60]

    @classmethod
    def align_window_with_future_labels(
        cls,
        window: TemporalWindowFeatures,
        ground_truth_events: List[Dict[str, Any]],  # List of {timestamp: datetime, threat_type: str, severity: str}
    ) -> FutureHorizonTarget:
        """Determines if attack events occurred in future forward windows."""
        window_end = window.window_end

        target = FutureHorizonTarget(
            window_id=window.window_id,
            target_timestamp=window_end,
        )

        for h in cls.HORIZONS_MINUTES:
            h_start = window_end
            h_end = window_end + timedelta(minutes=h)

            # Check if any ground truth attack occurred in [h_start, h_end]
            attacks_in_horizon = [
                ev for ev in ground_truth_events
                if h_start <= ev["timestamp"] <= h_end and ev.get("threat_type", "BENIGN") != "BENIGN"
            ]

            if attacks_in_horizon:
                threat_name = attacks_in_horizon[0]["threat_type"]
                if h == 5:
                    target.horizon_5m_threat = threat_name
                    target.horizon_5m_attack_occurred = True
                elif h == 15:
                    target.horizon_15m_threat = threat_name
                    target.horizon_15m_attack_occurred = True
                elif h == 30:
                    target.horizon_30m_threat = threat_name
                    target.horizon_30m_attack_occurred = True
                elif h == 60:
                    target.horizon_60m_threat = threat_name
                    target.horizon_60m_attack_occurred = True

        return target

    @classmethod
    def create_labeled_forecasting_dataset(
        cls,
        windows: List[TemporalWindowFeatures],
        ground_truth_events: List[Dict[str, Any]],
    ) -> List[Tuple[TemporalWindowFeatures, FutureHorizonTarget]]:
        """Pairs every temporal feature window with its forward multi-horizon target."""
        pairs: List[Tuple[TemporalWindowFeatures, FutureHorizonTarget]] = []
        for w in windows:
            label = cls.align_window_with_future_labels(w, ground_truth_events)
            pairs.append((w, label))
        return pairs
