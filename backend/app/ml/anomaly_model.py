"""Foresight AI - Behavioral Anomaly Detection Component.

Uses an unsupervised Isolation Forest model fit on baseline network traffic
to compute continuous behavioral deviation scores [0.0, 1.0].
"""

import os
from typing import Optional
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


class BehavioralAnomalyDetector:
    """Computes continuous network anomaly scores using an Isolation Forest."""

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
            max_samples="auto",
        )
        self.scaler = RobustScaler()
        self.is_fitted = False

    def fit(self, X: np.ndarray) -> "BehavioralAnomalyDetector":
        """Fits scaler and isolation forest on baseline training features."""
        if len(X) == 0:
            return self
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_fitted = True
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Calculates normalized anomaly scores in [0.0, 1.0]. Higher score = more anomalous."""
        if not self.is_fitted or len(X) == 0:
            return np.zeros(len(X), dtype=np.float32)

        X_scaled = self.scaler.transform(X)
        # raw decision_function: higher = normal, lower = anomalous
        raw_scores = self.model.decision_function(X_scaled)
        
        # Invert and normalize to [0.0, 1.0] using sigmoid-like scaling
        # Typical decision function is roughly in [-0.5, 0.5]
        normalized_scores = 1.0 / (1.0 + np.exp(raw_scores * 5.0))
        return np.clip(normalized_scores, 0.0, 1.0).astype(np.float32)

    def score_single(self, feature_vector: np.ndarray) -> float:
        """Scores a single feature vector."""
        vec_2d = feature_vector.reshape(1, -1)
        scores = self.score(vec_2d)
        return float(scores[0])

    def save(self, filepath: str) -> None:
        """Persists trained anomaly model artifact to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({"model": self.model, "scaler": self.scaler, "is_fitted": self.is_fitted}, filepath)

    def load(self, filepath: str) -> "BehavioralAnomalyDetector":
        """Loads serialized anomaly model artifact from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Anomaly model artifact not found at {filepath}")
        data = joblib.load(filepath)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.is_fitted = data.get("is_fitted", True)
        return self
