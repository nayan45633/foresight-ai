"""Foresight AI - Binary Split Conformal Prediction Engine (Step 4 & 4.1).

Provides finite-sample, distribution-free prediction sets with marginal coverage guarantees
under the assumption that calibration and test data are exchangeable:
- Non-conformity score: s_i = 1 - p(y_i | x_i)
- Conformal quantile: q_{1-alpha} = Quantile(s, ceil((n+1)(1-alpha))/n)
- Prediction set: Gamma(x) = {y in {0, 1} : (1 - p(y | x)) <= q_{1-alpha}}

Interpretation of Output Prediction Sets:
- {0}: Label 0 (benign) was not excluded by the conformal procedure at the 1 - alpha level.
- {1}: Label 1 (attack) was not excluded by the conformal procedure at the 1 - alpha level.
- {0, 1}: Neither label was excluded (forecast ambiguity / high uncertainty).
- []: Neither label satisfied the inclusion rule (high uncertainty / conformal rejection).

NOTE: Split Conformal Prediction provides marginal coverage across datasets, not an individual
posterior probability guarantee for any single prediction. Prediction sets serve as inputs
to downstream SOC policy decisions.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.ml.contracts import ConformalPredictionSet


class BinarySplitConformalPredictor:
    """Split Conformal Predictor for binary attack forecasting."""

    def __init__(self, target_coverage: float = 0.90):
        if not (0.50 <= target_coverage < 1.0):
            raise ValueError(f"Target coverage must be in [0.50, 1.0), got {target_coverage}")
        self.target_coverage = target_coverage
        self.quantile_threshold: Optional[float] = None
        self.calibration_sample_count: int = 0
        self.is_calibrated: bool = False

    def fit_calibration(self, calibrated_probs: np.ndarray, y_true: np.ndarray) -> "BinarySplitConformalPredictor":
        """Computes non-conformity scores and conformal quantile threshold on validation data."""
        n = len(y_true)
        if n == 0:
            self.is_calibrated = False
            return self

        # Non-conformity score: s_i = 1 - p(y_i | x_i)
        # For y=1: s_i = 1 - p_i
        # For y=0: s_i = p_i
        non_conformity_scores = np.where(y_true == 1, 1.0 - calibrated_probs, calibrated_probs)

        # Finite-sample adjusted conformal quantile level: ceil((n + 1) * (1 - alpha)) / n
        level = math.ceil((n + 1) * self.target_coverage) / float(n)
        level_clipped = min(1.0, max(0.0, level))

        # Compute empirical quantile
        self.quantile_threshold = float(np.quantile(non_conformity_scores, level_clipped, method="higher"))
        self.calibration_sample_count = n
        self.is_calibrated = True
        return self

    def predict_set(self, prob_attack: float) -> ConformalPredictionSet:
        """Constructs conformal prediction set for a given single calibrated probability."""
        if not self.is_calibrated or self.quantile_threshold is None:
            return ConformalPredictionSet(
                prediction_set=[0, 1],
                target_coverage=self.target_coverage,
                set_type="UNCERTAIN_AMBIGUOUS",
            )

        q = self.quantile_threshold
        pred_set: List[int] = []

        # Check if 0 (Benign) is in prediction set: s(0) = prob_attack <= q
        if prob_attack <= q:
            pred_set.append(0)

        # Check if 1 (Attack) is in prediction set: s(1) = (1 - prob_attack) <= q
        if (1.0 - prob_attack) <= q:
            pred_set.append(1)

        # Determine set type
        if pred_set == [0]:
            set_type = "SINGLETON_BENIGN"
        elif pred_set == [1]:
            set_type = "SINGLETON_ATTACK"
        elif set(pred_set) == {0, 1}:
            set_type = "UNCERTAIN_AMBIGUOUS"
        else:
            set_type = "HIGH_UNCERTAINTY_REJECTION"

        return ConformalPredictionSet(
            prediction_set=pred_set,
            target_coverage=self.target_coverage,
            set_type=set_type,
        )

    def evaluate_test_coverage(
        self, calibrated_probs: np.ndarray, y_true: np.ndarray
    ) -> Dict[str, Any]:
        """Evaluates empirical coverage and set-size efficiency on untouched held-out test data."""
        if not self.is_calibrated or len(y_true) == 0:
            return {
                "target_coverage": self.target_coverage,
                "empirical_coverage": None,
                "average_set_size": None,
                "singleton_rate": None,
                "ambiguous_rate": None,
                "empty_rate": None,
            }

        covered_count = 0
        set_sizes = []
        singleton_count = 0
        ambiguous_count = 0
        empty_count = 0
        n = len(y_true)

        for p, y in zip(calibrated_probs, y_true):
            c_set = self.predict_set(float(p))
            s = c_set.prediction_set
            set_sizes.append(len(s))

            if int(y) in s:
                covered_count += 1

            if len(s) == 1:
                singleton_count += 1
            elif len(s) == 2:
                ambiguous_count += 1
            elif len(s) == 0:
                empty_count += 1

        return {
            "target_coverage": round(self.target_coverage, 4),
            "empirical_coverage": round(covered_count / float(n), 4),
            "average_set_size": round(float(np.mean(set_sizes)), 4),
            "singleton_rate": round(singleton_count / float(n), 4),
            "ambiguous_rate": round(ambiguous_count / float(n), 4),
            "empty_rate": round(empty_count / float(n), 4),
            "sample_count": n,
            "quantile_threshold": round(self.quantile_threshold, 4),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes conformal predictor parameters."""
        return {
            "target_coverage": self.target_coverage,
            "quantile_threshold": self.quantile_threshold,
            "calibration_sample_count": self.calibration_sample_count,
            "is_calibrated": self.is_calibrated,
        }

