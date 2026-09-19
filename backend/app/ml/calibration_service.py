"""Foresight AI - Master Calibration & Conformal Experimentation Pipeline (Step 4).

Orchestrates:
1. Multi-candidate calibration evaluation (NoOp, Platt, Isotonic, Beta) on Validation partition ONLY.
2. Principled calibrator selection per horizon.
3. Split Conformal calibration for target coverage (e.g. 90%).
4. Principled operational threshold selection on Validation partition.
5. Final held-out evaluation on untouched test set.
6. Artifact persistence to separate models/, calibration/, conformal/, and metadata/ directories.
"""

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import RobustScaler

from app.core.config import settings
from app.core.logging import logger
from app.ml.anomaly_model import BehavioralAnomalyDetector
from app.ml.calibrators import (
    BaseCalibrator,
    BetaCalibrator,
    IsotonicCalibrator,
    NoOpCalibrator,
    PlattCalibrator,
    determine_calibration_status,
    evaluate_calibration_metrics,
)
from app.ml.conformal import BinarySplitConformalPredictor
from app.ml.contracts import (
    CalibrationHealthEnum,
    CalibrationHealthReport,
    CalibrationMethodEnum,
)
from app.ml.dataset_builder import ForecastingDatasetBuilder, TemporalForecastingDataset
from app.ml.train_pipeline import generate_benchmark_timeline
from app.telemetry.window_generator import SlidingWindowGenerator


class CalibrationExperimentEngine:
    """Experimentation and persistence engine for model calibration and uncertainty."""

    HORIZONS = [5, 15, 30, 60]

    def __init__(
        self,
        model_version: str = "v1.0.0-temporal-gbm",
        target_coverage: float = 0.90,
        random_state: int = 42,
    ):
        self.model_version = model_version
        self.target_coverage = target_coverage
        self.random_state = random_state

        self.scaler = RobustScaler()
        self.anomaly_detector = BehavioralAnomalyDetector(random_state=random_state)

        self.horizon_models: Dict[int, HistGradientBoostingClassifier] = {}
        self.horizon_calibrators: Dict[int, BaseCalibrator] = {}
        self.horizon_conformal: Dict[int, BinarySplitConformalPredictor] = {}
        self.horizon_thresholds: Dict[int, float] = {}

        self.validation_experiments: Dict[int, Dict[str, Any]] = {}
        self.validation_health_reports: Dict[int, CalibrationHealthReport] = {}
        self.test_evaluation_reports: Dict[int, Dict[str, Any]] = {}

    def run_full_pipeline(
        self,
        train_set: TemporalForecastingDataset,
        val_set: TemporalForecastingDataset,
        test_set: TemporalForecastingDataset,
    ) -> Dict[str, Any]:
        """Runs candidate evaluation on validation, freezes selected methods, and evaluates on test."""
        logger.info("==================================================================")
        logger.info("FORESIGHT AI — STEP 4 CALIBRATION & CONFORMAL EXPERIMENT PIPELINE")
        logger.info("==================================================================")

        # 1. Fit Anomaly Model & Scaler on Train partition
        self.anomaly_detector.fit(train_set.X)
        tr_anom = self.anomaly_detector.score(train_set.X).reshape(-1, 1)
        val_anom = self.anomaly_detector.score(val_set.X).reshape(-1, 1)
        test_anom = self.anomaly_detector.score(test_set.X).reshape(-1, 1)

        X_tr = self.scaler.fit_transform(np.hstack([train_set.X, tr_anom]))
        X_val = self.scaler.transform(np.hstack([val_set.X, val_anom]))
        X_test = self.scaler.transform(np.hstack([test_set.X, test_anom]))

        # 2. Train Base Models and Run Validation Calibration Experiments
        for h in self.HORIZONS:
            y_tr = train_set.y_horizons[h]
            y_val = val_set.y_horizons[h]

            # Fit base HistGBM model
            base_model = HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_iter=150,
                max_leaf_nodes=31,
                min_samples_leaf=10,
                class_weight="balanced",
                random_state=self.random_state,
            )
            base_model.fit(X_tr, y_tr)
            self.horizon_models[h] = base_model

            # Raw probabilities on validation partition
            raw_val_probs = base_model.predict_proba(X_val)[:, 1]

            # Evaluate Candidate Calibration Methods on Validation data
            candidates: Dict[str, BaseCalibrator] = {
                "NONE": NoOpCalibrator(),
                "PLATT_SIGMOID": PlattCalibrator(),
                "ISOTONIC": IsotonicCalibrator(),
                "BETA": BetaCalibrator(),
            }

            candidate_metrics: Dict[str, Any] = {}
            for name, cal in candidates.items():
                cal.fit(raw_val_probs, y_val)
                cal_probs = cal.predict_proba(raw_val_probs)
                metrics = evaluate_calibration_metrics(y_val, cal_probs)
                candidate_metrics[name] = {
                    "brier_score": metrics["brier_score"],
                    "expected_calibration_error": metrics["expected_calibration_error"],
                    "maximum_calibration_error": metrics["maximum_calibration_error"],
                    "log_loss": metrics["log_loss"],
                }

            self.validation_experiments[h] = candidate_metrics

            # Principled selection on Validation data (Minimizing Brier score and ECE)
            # For 5m: Platt/Beta helps stabilize extreme imbalance; For 15m/30m: Platt/Isotonic
            best_method_name = min(
                candidates.keys(),
                key=lambda k: candidate_metrics[k]["brier_score"] + candidate_metrics[k]["expected_calibration_error"]
            )
            selected_calibrator = candidates[best_method_name]
            self.horizon_calibrators[h] = selected_calibrator

            calibrated_val_probs = selected_calibrator.predict_proba(raw_val_probs)
            val_cal_metrics = evaluate_calibration_metrics(y_val, calibrated_val_probs)

            # Fit Split Conformal Predictor on Validation partition
            conformal_pred = BinarySplitConformalPredictor(target_coverage=self.target_coverage)
            conformal_pred.fit_calibration(calibrated_val_probs, y_val)
            self.horizon_conformal[h] = conformal_pred

            # Principled Operational Threshold Selection on Validation partition
            # Search over unique step values and quantile percentiles of calibrated validation predictions
            candidate_thresholds = np.unique(
                np.concatenate([
                    np.unique(calibrated_val_probs),
                    np.quantile(calibrated_val_probs, np.linspace(0.01, 0.99, 100))
                ])
            )
            best_th = 0.5
            best_f1 = -1.0

            for th in candidate_thresholds:
                preds = (calibrated_val_probs >= th).astype(int)
                f1 = f1_score(y_val, preds, zero_division=0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_th = float(th)

            # Fallback if all F1s are 0: set threshold to median positive probability or 0.5
            if best_f1 <= 0.0 and np.sum(y_val) > 0:
                pos_val_probs = calibrated_val_probs[y_val == 1]
                best_th = float(np.median(pos_val_probs)) if len(pos_val_probs) > 0 else 0.5

            self.horizon_thresholds[h] = best_th

            status = determine_calibration_status(
                val_cal_metrics["expected_calibration_error"], val_cal_metrics["brier_score"]
            )

            self.validation_health_reports[h] = CalibrationHealthReport(
                horizon_minutes=h,
                calibration_method=CalibrationMethodEnum(best_method_name),
                brier_score=val_cal_metrics["brier_score"],
                expected_calibration_error=val_cal_metrics["expected_calibration_error"],
                maximum_calibration_error=val_cal_metrics["maximum_calibration_error"],
                log_loss=val_cal_metrics["log_loss"],
                status=status,
                reliability_bins=val_cal_metrics["reliability_bins"],
                conformal_target_coverage=self.target_coverage,
                sample_count=len(y_val),
            )

            logger.info(
                f"Horizon +{h}m: Selected {best_method_name} | Val Brier: {val_cal_metrics['brier_score']:.4f} | Val ECE: {val_cal_metrics['expected_calibration_error']:.4f} | Optimal Thresh: {best_th:.4f}"
            )

        # 3. Final Step 4 Evaluation on Held-Out Test Set (Evaluated ONCE)
        logger.info("Evaluating frozen models, calibrators, and conformal predictors on Held-Out Test partition...")
        for h in self.HORIZONS:
            y_test = test_set.y_horizons[h]
            base_model = self.horizon_models[h]
            calibrator = self.horizon_calibrators[h]
            conformal_pred = self.horizon_conformal[h]
            th = self.horizon_thresholds[h]

            raw_test_probs = base_model.predict_proba(X_test)[:, 1]
            cal_test_probs = calibrator.predict_proba(raw_test_probs)

            # Calibration metrics on test
            cal_metrics = evaluate_calibration_metrics(y_test, cal_test_probs)

            # Conformal coverage on test
            conformal_metrics = conformal_pred.evaluate_test_coverage(cal_test_probs, y_test)

            # Classification metrics on test
            preds = (cal_test_probs >= th).astype(int)
            prec = float(precision_score(y_test, preds, zero_division=0))
            rec = float(recall_score(y_test, preds, zero_division=0))
            f1 = float(f1_score(y_test, preds, zero_division=0))
            pr_auc = float(average_precision_score(y_test, cal_test_probs)) if len(np.unique(y_test)) > 1 else 0.0
            roc_auc = float(roc_auc_score(y_test, cal_test_probs)) if len(np.unique(y_test)) > 1 else 0.5
            cm = confusion_matrix(y_test, preds).tolist()

            status = determine_calibration_status(
                cal_metrics["expected_calibration_error"], cal_metrics["brier_score"]
            )

            self.test_evaluation_reports[h] = {
                "horizon_minutes": h,
                "calibration_method": calibrator.method_name.value,
                "threshold": round(th, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "pr_auc": round(pr_auc, 4),
                "roc_auc": round(roc_auc, 4),
                "brier_score": cal_metrics["brier_score"],
                "expected_calibration_error": cal_metrics["expected_calibration_error"],
                "maximum_calibration_error": cal_metrics["maximum_calibration_error"],
                "log_loss": cal_metrics["log_loss"],
                "status": status.value,
                "conformal_target_coverage": conformal_metrics["target_coverage"],
                "conformal_empirical_coverage": conformal_metrics["empirical_coverage"],
                "conformal_average_set_size": conformal_metrics["average_set_size"],
                "singleton_rate": conformal_metrics["singleton_rate"],
                "ambiguous_rate": conformal_metrics["ambiguous_rate"],
                "confusion_matrix": cm,
                "sample_count": len(y_test),
            }

        return {
            "validation_experiments": self.validation_experiments,
            "validation_health_reports": {h: r.model_dump() for h, r in self.validation_health_reports.items()},
            "held_out_test_reports": self.test_evaluation_reports,
        }

    def save_all_artifacts(self, base_dir: str = "./artifacts") -> Dict[str, str]:
        """Saves models, calibrators, conformal quantiles, and health metadata into clean subdirectories."""
        models_dir = os.path.join(base_dir, "models")
        calib_dir = os.path.join(base_dir, "calibration")
        conformal_dir = os.path.join(base_dir, "conformal")
        meta_dir = os.path.join(base_dir, "metadata")

        for d in [models_dir, calib_dir, conformal_dir, meta_dir]:
            os.makedirs(d, exist_ok=True)

        # 1. Save Base Models Bundle
        model_bundle = {
            "model_version": self.model_version,
            "scaler": self.scaler,
            "anomaly_detector": self.anomaly_detector,
            "horizon_models": self.horizon_models,
            "horizon_thresholds": self.horizon_thresholds,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        model_path = os.path.join(models_dir, f"{self.model_version}.joblib")
        joblib.dump(model_bundle, model_path)

        # 2. Save Calibrators
        calib_bundle = {
            "model_version": self.model_version,
            "calibrators": self.horizon_calibrators,
            "methods": {h: c.method_name.value for h, c in self.horizon_calibrators.items()},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        calib_path = os.path.join(calib_dir, f"{self.model_version}_calibration.joblib")
        joblib.dump(calib_bundle, calib_path)

        # 3. Save Conformal Predictors
        conformal_bundle = {
            "model_version": self.model_version,
            "target_coverage": self.target_coverage,
            "predictors": self.horizon_conformal,
            "quantiles": {h: p.quantile_threshold for h, p in self.horizon_conformal.items()},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        conformal_path = os.path.join(conformal_dir, f"{self.model_version}_conformal.joblib")
        joblib.dump(conformal_bundle, conformal_path)

        # 4. Save Step 4 Metadata & Calibration Health JSON
        meta_json = {
            "model_version": self.model_version,
            "step": "STEP 4: CALIBRATION & UNCERTAINTY QUANTIFICATION",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "target_coverage": self.target_coverage,
            "validation_experiments": self.validation_experiments,
            "validation_health_reports": {h: r.model_dump() for h, r in self.validation_health_reports.items()},
            "held_out_test_reports": self.test_evaluation_reports,
            "horizon_thresholds": self.horizon_thresholds,
        }
        meta_path = os.path.join(meta_dir, f"{self.model_version}_step4_calibration_report.json")
        with open(meta_path, "w") as f:
            json.dump(meta_json, f, indent=2, default=str)

        logger.info(f"Step 4 Artifacts persisted successfully in {base_dir}")
        return {
            "model_artifact": model_path,
            "calibration_artifact": calib_path,
            "conformal_artifact": conformal_path,
            "metadata_artifact": meta_path,
        }


def run_step4_calibration_pipeline():
    """Runs data generation, calibration experimentation, and artifact serialization."""
    flows, gt = generate_benchmark_timeline(total_hours=24, flows_per_minute=35, random_seed=42)
    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flows)
    builder = ForecastingDatasetBuilder(rolling_context_steps=4)
    dataset = builder.build_dataset_from_windows(windows, gt)
    train_set, val_set, test_set = builder.chronological_train_val_test_split(dataset, train_ratio=0.70, val_ratio=0.15)

    engine = CalibrationExperimentEngine(model_version="v1.0.0-temporal-gbm", target_coverage=0.90, random_state=42)
    results = engine.run_full_pipeline(train_set, val_set, test_set)
    artifacts = engine.save_all_artifacts(base_dir="./artifacts")

    print("\n" + "=" * 90)
    print("FORESIGHT AI — STEP 4 CALIBRATION & CONFORMAL EVALUATION (HELD-OUT TEST SET)")
    print("=" * 90)
    print(f"{'Horizon':<8} | {'Method':<14} | {'Thresh':<7} | {'Brier':<8} | {'ECE':<8} | {'F1':<7} | {'Coverage':<9} | {'Avg Set Size':<12} | {'Status':<10}")
    print("-" * 90)
    for h, r in results["held_out_test_reports"].items():
        cov_str = f"{r['conformal_empirical_coverage']*100:.1f}%" if r['conformal_empirical_coverage'] is not None else "N/A"
        print(f"{str(h)+'m':<8} | {r['calibration_method']:<14} | {r['threshold']:<7.4f} | {r['brier_score']:<8.4f} | {r['expected_calibration_error']:<8.4f} | {r['f1']:<7.4f} | {cov_str:<9} | {r['conformal_average_set_size']:<12.2f} | {r['status']:<10}")
    print("=" * 90 + "\n")

    return engine, results, artifacts


if __name__ == "__main__":
    run_step4_calibration_pipeline()
