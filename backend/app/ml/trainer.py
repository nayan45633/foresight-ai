"""Foresight AI - Core ML Training, Calibration & Evaluation Pipeline.

Trains multi-horizon temporal attack forecasting models (5m, 15m, 30m, 60m):
- Evaluates baselines (Majority, Logistic Regression, Random Forest)
- Trains Gradient Boosted production models with balanced class weighting
- Implements explicit probability calibration (Platt Sigmoid / Isotonic Regression)
- Computes Brier Score, Expected Calibration Error (ECE), F1, PR-AUC, and ROC-AUC
- Serializes model artifacts and metadata
"""

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from app.core.logging import logger
from app.ml.anomaly_model import BehavioralAnomalyDetector
from app.ml.dataset_builder import TemporalForecastingDataset


class PlattCalibrator:
    """Explicit Platt scaling calibrator fit on validation model probabilities."""

    def __init__(self):
        self.lr = LogisticRegression(solver="lbfgs")
        self.is_fitted = False

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "PlattCalibrator":
        if len(np.unique(y_true)) < 2:
            self.is_fitted = False
            return self
        X = raw_probs.reshape(-1, 1)
        self.lr.fit(X, y_true)
        self.is_fitted = True
        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return raw_probs
        X = raw_probs.reshape(-1, 1)
        return self.lr.predict_proba(X)[:, 1]


class HorizonEvaluationMetrics:
    """Evaluation metrics for a specific forecasting horizon."""

    def __init__(
        self,
        horizon_minutes: int,
        precision: float,
        recall: float,
        f1: float,
        pr_auc: float,
        roc_auc: float,
        brier_score: float,
        expected_calibration_error: float,
        confusion_mat: List[List[int]],
        threshold: float,
    ):
        self.horizon_minutes = horizon_minutes
        self.precision = precision
        self.recall = recall
        self.f1 = f1
        self.pr_auc = pr_auc
        self.roc_auc = roc_auc
        self.brier_score = brier_score
        self.expected_calibration_error = expected_calibration_error
        self.confusion_mat = confusion_mat
        self.threshold = threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_minutes": self.horizon_minutes,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "pr_auc": round(self.pr_auc, 4),
            "roc_auc": round(self.roc_auc, 4),
            "brier_score": round(self.brier_score, 4),
            "expected_calibration_error": round(self.expected_calibration_error, 4),
            "confusion_matrix": self.confusion_mat,
            "optimal_threshold": round(self.threshold, 4),
        }


class ModelTrainer:
    """Orchestrates model training, multi-horizon calibration, and evaluation."""

    HORIZONS = [5, 15, 30, 60]

    def __init__(self, model_version: str = "v1.0.0-temporal-gbm", random_state: int = 42):
        self.model_version = model_version
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.anomaly_detector = BehavioralAnomalyDetector(random_state=random_state)
        self.horizon_models: Dict[int, Any] = {}
        self.horizon_calibrators: Dict[int, PlattCalibrator] = {}
        self.horizon_thresholds: Dict[int, float] = {}
        self.metrics_summary: Dict[int, Dict[str, Any]] = {}
        self.baseline_metrics: Dict[str, Dict[int, Dict[str, float]]] = {}

    @staticmethod
    def calculate_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
        """Calculates Expected Calibration Error (ECE) across confidence bins."""
        if len(y_true) == 0:
            return 0.0
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        n = len(y_true)

        for i in range(n_bins):
            bin_mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
            if np.sum(bin_mask) > 0:
                bin_acc = np.mean(y_true[bin_mask])
                bin_conf = np.mean(y_prob[bin_mask])
                bin_weight = np.sum(bin_mask) / n
                ece += bin_weight * abs(bin_acc - bin_conf)
        return float(ece)

    def evaluate_baselines(
        self, train_set: TemporalForecastingDataset, val_set: TemporalForecastingDataset
    ) -> Dict[str, Any]:
        """Evaluates Dummy and Logistic Regression baselines across all horizons."""
        X_tr = self.scaler.fit_transform(train_set.X)
        X_val = self.scaler.transform(val_set.X)

        results: Dict[str, Any] = {"majority_class": {}, "logistic_regression": {}, "random_forest": {}}

        for h in self.HORIZONS:
            y_tr = train_set.y_horizons[h]
            y_val = val_set.y_horizons[h]

            if len(np.unique(y_tr)) < 2:
                continue

            # 1. Majority class baseline
            dummy = DummyClassifier(strategy="most_frequent")
            dummy.fit(X_tr, y_tr)
            y_pred_dummy = dummy.predict(X_val)
            results["majority_class"][h] = {
                "f1": float(f1_score(y_val, y_pred_dummy, zero_division=0)),
                "brier": float(brier_score_loss(y_val, dummy.predict_proba(X_val)[:, 1])),
            }

            # 2. Simple Logistic Regression
            lr = LogisticRegression(class_weight="balanced", max_iter=500, random_state=self.random_state)
            lr.fit(X_tr, y_tr)
            y_prob_lr = lr.predict_proba(X_val)[:, 1]
            y_pred_lr = (y_prob_lr >= 0.5).astype(int)
            results["logistic_regression"][h] = {
                "f1": float(f1_score(y_val, y_pred_lr, zero_division=0)),
                "brier": float(brier_score_loss(y_val, y_prob_lr)),
                "roc_auc": float(roc_auc_score(y_val, y_prob_lr)) if len(np.unique(y_val)) > 1 else 0.5,
            }

            # 3. Random Forest baseline
            rf = RandomForestClassifier(n_estimators=50, max_depth=8, class_weight="balanced", random_state=self.random_state)
            rf.fit(X_tr, y_tr)
            y_prob_rf = rf.predict_proba(X_val)[:, 1]
            y_pred_rf = (y_prob_rf >= 0.5).astype(int)
            results["random_forest"][h] = {
                "f1": float(f1_score(y_val, y_pred_rf, zero_division=0)),
                "brier": float(brier_score_loss(y_val, y_prob_rf)),
                "roc_auc": float(roc_auc_score(y_val, y_prob_rf)) if len(np.unique(y_val)) > 1 else 0.5,
            }

        self.baseline_metrics = results
        return results

    def train_and_calibrate(
        self,
        train_set: TemporalForecastingDataset,
        val_set: TemporalForecastingDataset,
    ) -> Dict[int, HorizonEvaluationMetrics]:
        """Trains HistGradientBoosting models and calibrates probabilities per horizon."""
        logger.info(f"Training multi-horizon forecasting models for {self.model_version}...")

        # 1. Fit Anomaly Detector on Train features
        self.anomaly_detector.fit(train_set.X)

        # Compute anomaly features for enrichment
        tr_anom = self.anomaly_detector.score(train_set.X).reshape(-1, 1)
        val_anom = self.anomaly_detector.score(val_set.X).reshape(-1, 1)

        X_tr_enriched = np.hstack([train_set.X, tr_anom])
        X_val_enriched = np.hstack([val_set.X, val_anom])

        X_tr_scaled = self.scaler.fit_transform(X_tr_enriched)
        X_val_scaled = self.scaler.transform(X_val_enriched)

        evaluation_results: Dict[int, HorizonEvaluationMetrics] = {}

        for h in self.HORIZONS:
            y_tr = train_set.y_horizons[h]
            y_val = val_set.y_horizons[h]

            # Train Gradient Boosted Forecaster
            base_model = HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_iter=150,
                max_leaf_nodes=31,
                min_samples_leaf=10,
                class_weight="balanced",
                random_state=self.random_state,
            )
            base_model.fit(X_tr_scaled, y_tr)

            # Raw probabilities on validation set
            raw_prob_val = base_model.predict_proba(X_val_scaled)[:, 1]
            raw_brier = brier_score_loss(y_val, raw_prob_val)
            raw_ece = self.calculate_ece(y_val, raw_prob_val)

            # Fit Platt Calibrator on Validation data
            calibrator = PlattCalibrator()
            calibrator.fit(raw_prob_val, y_val)
            calibrated_prob_val = calibrator.predict_proba(raw_prob_val)

            cal_brier = brier_score_loss(y_val, calibrated_prob_val)
            cal_ece = self.calculate_ece(y_val, calibrated_prob_val)

            logger.info(
                f"Horizon {h}m Calibration: Brier {raw_brier:.4f} -> {cal_brier:.4f}, ECE {raw_ece:.4f} -> {cal_ece:.4f}"
            )

            # Select optimal operational decision threshold on Validation set (maximizing F1)
            best_threshold = 0.5
            best_f1 = 0.0
            for th in np.linspace(0.2, 0.8, 31):
                preds = (calibrated_prob_val >= th).astype(int)
                score = f1_score(y_val, preds, zero_division=0)
                if score > best_f1:
                    best_f1 = score
                    best_threshold = float(th)

            # Store models & thresholds
            self.horizon_models[h] = base_model
            self.horizon_calibrators[h] = calibrator
            self.horizon_thresholds[h] = best_threshold

            # Validation Metrics
            final_preds = (calibrated_prob_val >= best_threshold).astype(int)
            prec = float(precision_score(y_val, final_preds, zero_division=0))
            rec = float(recall_score(y_val, final_preds, zero_division=0))
            f1_val = float(f1_score(y_val, final_preds, zero_division=0))
            pr_auc = float(average_precision_score(y_val, calibrated_prob_val)) if len(np.unique(y_val)) > 1 else 0.0
            roc_auc = float(roc_auc_score(y_val, calibrated_prob_val)) if len(np.unique(y_val)) > 1 else 0.5
            cm = confusion_matrix(y_val, final_preds).tolist()

            metrics_obj = HorizonEvaluationMetrics(
                horizon_minutes=h,
                precision=prec,
                recall=rec,
                f1=f1_val,
                pr_auc=pr_auc,
                roc_auc=roc_auc,
                brier_score=cal_brier,
                expected_calibration_error=cal_ece,
                confusion_mat=cm,
                threshold=best_threshold,
            )
            evaluation_results[h] = metrics_obj
            self.metrics_summary[h] = metrics_obj.to_dict()

        return evaluation_results

    def evaluate_test_set_once(self, test_set: TemporalForecastingDataset) -> Dict[int, Dict[str, Any]]:
        """Evaluates final calibrated models ONCE on untouched held-out test partition."""
        test_anom = self.anomaly_detector.score(test_set.X).reshape(-1, 1)
        X_test_enriched = np.hstack([test_set.X, test_anom])
        X_test_scaled = self.scaler.transform(X_test_enriched)

        final_test_metrics: Dict[int, Dict[str, Any]] = {}

        for h in self.HORIZONS:
            y_test = test_set.y_horizons[h]
            base_model = self.horizon_models[h]
            calibrator = self.horizon_calibrators[h]
            th = self.horizon_thresholds[h]

            raw_prob_test = base_model.predict_proba(X_test_scaled)[:, 1]
            prob_test = calibrator.predict_proba(raw_prob_test)
            preds = (prob_test >= th).astype(int)

            prec = float(precision_score(y_test, preds, zero_division=0))
            rec = float(recall_score(y_test, preds, zero_division=0))
            f1_t = float(f1_score(y_test, preds, zero_division=0))
            pr_auc = float(average_precision_score(y_test, prob_test)) if len(np.unique(y_test)) > 1 else 0.0
            roc_auc = float(roc_auc_score(y_test, prob_test)) if len(np.unique(y_test)) > 1 else 0.5
            brier = float(brier_score_loss(y_test, prob_test))
            ece = float(self.calculate_ece(y_test, prob_test))
            cm = confusion_matrix(y_test, preds).tolist()

            final_test_metrics[h] = {
                "horizon_minutes": h,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1_t, 4),
                "pr_auc": round(pr_auc, 4),
                "roc_auc": round(roc_auc, 4),
                "brier_score": round(brier, 4),
                "expected_calibration_error": round(ece, 4),
                "confusion_matrix": cm,
                "threshold": round(th, 4),
            }

        return final_test_metrics

    def save_artifacts(self, artifact_dir: str = "artifacts/models") -> str:
        """Saves models, scalers, anomaly detector, thresholds, and metadata to disk."""
        os.makedirs(artifact_dir, exist_ok=True)
        model_path = os.path.join(artifact_dir, f"{self.model_version}.joblib")
        meta_path = os.path.join(artifact_dir, f"{self.model_version}_metadata.json")

        bundle = {
            "model_version": self.model_version,
            "scaler": self.scaler,
            "anomaly_detector": self.anomaly_detector,
            "horizon_models": self.horizon_models,
            "horizon_calibrators": self.horizon_calibrators,
            "horizon_thresholds": self.horizon_thresholds,
            "horizons": self.HORIZONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        joblib.dump(bundle, model_path)

        metadata = {
            "model_version": self.model_version,
            "model_architecture": "EnsembleHistGradientBoostingClassifier",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "supported_horizons": self.HORIZONS,
            "validation_metrics": self.metrics_summary,
            "baseline_metrics": self.baseline_metrics,
            "hyperparameters": {
                "learning_rate": 0.05,
                "max_iter": 150,
                "max_leaf_nodes": 31,
                "calibration": "PlattSigmoid",
            },
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Artifacts successfully saved to {model_path} and {meta_path}")
        return model_path
