"""Foresight AI - Advanced Probability Calibration Engine (Step 4).

Implements and evaluates candidate calibration models:
1. NoOpCalibrator (Identity baseline)
2. PlattCalibrator (Logistic Sigmoid scaling)
3. IsotonicCalibrator (Non-parametric piecewise constant isotonic regression)
4. BetaCalibrator (Bivariate logistic regression on log-odds features)

Also provides calibration metric evaluators:
- Brier Score
- Expected Calibration Error (ECE)
- Maximum Calibration Error (MCE)
- Log Loss / Binary Cross-Entropy
- Calibration Slope & Intercept
- Reliability Diagram Bin Statistics
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from app.ml.contracts import (
    CalibrationHealthEnum,
    CalibrationMethodEnum,
    ReliabilityBinData,
)


class BaseCalibrator(ABC):
    """Abstract base class for probability calibrators."""

    def __init__(self, method_name: CalibrationMethodEnum):
        self.method_name = method_name
        self.is_fitted = False

    @abstractmethod
    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "BaseCalibrator":
        """Fits calibration model on validation probabilities and labels."""
        pass

    @abstractmethod
    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        """Transforms raw probabilities to calibrated probabilities bounded in [0.0, 1.0]."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serializes calibrator metadata and parameters."""
        return {
            "method_name": self.method_name.value,
            "is_fitted": self.is_fitted,
        }


class NoOpCalibrator(BaseCalibrator):
    """Identity calibrator that passes raw probabilities through unchanged."""

    def __init__(self):
        super().__init__(CalibrationMethodEnum.NONE)

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "NoOpCalibrator":
        self.is_fitted = True
        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        return np.clip(np.nan_to_num(raw_probs, nan=0.0), 0.0, 1.0)


class PlattCalibrator(BaseCalibrator):
    """Explicit Platt scaling calibrator fit using logistic regression on raw probabilities."""

    def __init__(self):
        super().__init__(CalibrationMethodEnum.PLATT_SIGMOID)
        self.lr = LogisticRegression(solver="lbfgs", C=1.0, max_iter=500)
        self.slope: Optional[float] = None
        self.intercept: Optional[float] = None

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "PlattCalibrator":
        if len(np.unique(y_true)) < 2:
            self.is_fitted = False
            return self
        X = raw_probs.reshape(-1, 1)
        self.lr.fit(X, y_true)
        self.slope = float(self.lr.coef_[0, 0])
        self.intercept = float(self.lr.intercept_[0])
        self.is_fitted = True
        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.clip(raw_probs, 0.0, 1.0)
        X = raw_probs.reshape(-1, 1)
        probs = self.lr.predict_proba(X)[:, 1]
        return np.clip(probs, 0.0, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "slope": self.slope,
            "intercept": self.intercept,
        })
        return d


class IsotonicCalibrator(BaseCalibrator):
    """Piecewise constant non-parametric isotonic regression calibrator."""

    def __init__(self):
        super().__init__(CalibrationMethodEnum.ISOTONIC)
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        if len(np.unique(y_true)) < 2:
            self.is_fitted = False
            return self
        self.iso.fit(raw_probs, y_true)
        self.is_fitted = True
        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.clip(raw_probs, 0.0, 1.0)
        probs = self.iso.predict(raw_probs)
        return np.clip(probs, 0.0, 1.0)


class BetaCalibrator(BaseCalibrator):
    """Beta calibration suited for imbalanced probabilities (Kull et al. 2017).
    
    Transforms p to feature vector [ln(p), -ln(1-p)] and fits a logistic regression.
    """

    def __init__(self):
        super().__init__(CalibrationMethodEnum.BETA)
        self.lr = LogisticRegression(solver="lbfgs", max_iter=500)
        self.eps = 1e-6
        self.coef_: Optional[List[float]] = None
        self.intercept_: Optional[float] = None

    def _transform_features(self, p: np.ndarray) -> np.ndarray:
        p_clipped = np.clip(p, self.eps, 1.0 - self.eps)
        feat1 = np.log(p_clipped)
        feat2 = -np.log(1.0 - p_clipped)
        return np.column_stack([feat1, feat2])

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "BetaCalibrator":
        if len(np.unique(y_true)) < 2:
            self.is_fitted = False
            return self
        X = self._transform_features(raw_probs)
        self.lr.fit(X, y_true)
        self.coef_ = self.lr.coef_[0].tolist()
        self.intercept_ = float(self.lr.intercept_[0])
        self.is_fitted = True
        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.clip(raw_probs, 0.0, 1.0)
        X = self._transform_features(raw_probs)
        probs = self.lr.predict_proba(X)[:, 1]
        return np.clip(probs, 0.0, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "coefficients": self.coef_,
            "intercept": self.intercept_,
        })
        return d


def calculate_ece_mce_and_bins(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, float, List[ReliabilityBinData]]:
    """Computes Expected Calibration Error (ECE), Maximum Calibration Error (MCE), and reliability diagram bins."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    n_samples = len(probs)
    bins_data: List[ReliabilityBinData] = []

    if n_samples == 0:
        return 0.0, 0.0, []

    for i in range(n_bins):
        low = float(bin_edges[i])
        high = float(bin_edges[i + 1])
        # Include right edge for last bin
        if i == n_bins - 1:
            mask = (probs >= low) & (probs <= high)
        else:
            mask = (probs >= low) & (probs < high)

        count = int(np.sum(mask))
        if count > 0:
            obs_freq = float(np.mean(y_true[mask]))
            mean_prob = float(np.mean(probs[mask]))
            cal_err = abs(obs_freq - mean_prob)
            ece += (count / n_samples) * cal_err
            if cal_err > mce:
                mce = cal_err
        else:
            obs_freq = 0.0
            mean_prob = float((low + high) / 2.0)
            cal_err = 0.0

        bins_data.append(ReliabilityBinData(
            bin_lower=round(low, 2),
            bin_upper=round(high, 2),
            sample_count=count,
            mean_predicted_probability=round(mean_prob, 4),
            observed_positive_frequency=round(obs_freq, 4),
            absolute_calibration_error=round(cal_err, 4),
        ))

    return round(float(ece), 4), round(float(mce), 4), bins_data


def evaluate_calibration_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Calculates full suite of calibration performance metrics."""
    probs_safe = np.clip(probs, 1e-7, 1.0 - 1e-7)
    brier = float(brier_score_loss(y_true, probs_safe))
    loss_val = float(log_loss(y_true, probs_safe, labels=[0, 1]))
    ece, mce, bins = calculate_ece_mce_and_bins(y_true, probs, n_bins=n_bins)

    # Calibration slope & intercept via logistic regression
    if len(np.unique(y_true)) > 1 and len(np.unique(probs)) > 1:
        lr_diag = LogisticRegression(solver="lbfgs")
        X_diag = np.clip(probs, 1e-5, 1.0 - 1e-5).reshape(-1, 1)
        lr_diag.fit(X_diag, y_true)
        slope = float(lr_diag.coef_[0, 0])
        intercept = float(lr_diag.intercept_[0])
    else:
        slope = 1.0
        intercept = 0.0

    return {
        "brier_score": round(brier, 4),
        "expected_calibration_error": ece,
        "maximum_calibration_error": mce,
        "log_loss": round(loss_val, 4),
        "calibration_slope": round(slope, 4),
        "calibration_intercept": round(intercept, 4),
        "reliability_bins": bins,
    }


def determine_calibration_status(ece: float, brier: float) -> CalibrationHealthEnum:
    """Assigns deterministic calibration health status based on validated rules."""
    if ece <= 0.05 and brier <= 0.10:
        return CalibrationHealthEnum.CALIBRATED
    elif ece <= 0.08:
        return CalibrationHealthEnum.WATCH
    else:
        return CalibrationHealthEnum.LIMITED
