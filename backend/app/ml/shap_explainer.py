"""Foresight AI - Real TreeSHAP Multi-Horizon Explainability Engine (Step 5).

Provides mathematically grounded feature attribution for HistGradientBoosting models:
- TreeExplainer implementation natively supported by gradient boosted decision trees.
- Exact TreeSHAP additivity in raw margin space: base_value + sum(shap_values) == decision_function(x).
- Multi-horizon explanation separation (5m, 15m, 30m, 60m).
- Top positive (risk-increasing) and top negative (risk-decreasing) attribution ranking.
- Deterministic, human-readable feature interpretation grounded in observed telemetry.
- Global and horizon-specific feature importance benchmarking.
"""

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import shap
from sklearn.ensemble import HistGradientBoostingClassifier

from app.ml.contracts import FeatureContribution
from app.ml.feature_schema import (
    FEATURE_DEFINITIONS,
    FEATURE_INDEX_TO_DEF,
    FEATURE_NAME_TO_INDEX,
    SCHEMA_VERSION,
    get_feature_names,
    validate_feature_vector,
)

logger = logging.getLogger("foresight.ml.shap")


class HorizonShapExplainer:
    """Multi-horizon TreeSHAP explainability engine for Foresight AI forecasters."""

    HORIZONS = [5, 15, 30, 60]

    def __init__(
        self,
        horizon_models: Optional[Dict[int, HistGradientBoostingClassifier]] = None,
        model_version: str = "v1.0.0-temporal-gbm",
    ):
        self.model_version = model_version
        self.schema_version = SCHEMA_VERSION
        self.horizon_models: Dict[int, HistGradientBoostingClassifier] = horizon_models or {}
        self.horizon_explainers: Dict[int, shap.TreeExplainer] = {}
        self.global_importance_cache: Optional[Dict[str, Any]] = None
        self.is_initialized: bool = False

        if self.horizon_models:
            self._init_explainers()

    def _init_explainers(self) -> None:
        """Initializes cached TreeExplainer objects for each horizon model."""
        for h, model in self.horizon_models.items():
            try:
                explainer = shap.TreeExplainer(model)
                self.horizon_explainers[h] = explainer
                logger.info(f"TreeSHAP explainer initialized for horizon +{h}m.")
            except Exception as e:
                logger.error(f"Failed to initialize TreeSHAP explainer for +{h}m: {e}", exc_info=True)

        self.is_initialized = len(self.horizon_explainers) > 0

    def explain_instance(
        self,
        scaled_features: np.ndarray,
        raw_features: np.ndarray,
        horizon_minutes: int,
        calibrated_probability: float,
        raw_probability: Optional[float] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Generates exact TreeSHAP feature attributions for a single telemetry window."""
        start_time = time.perf_counter()

        # Validate input shapes and finiteness
        X_scaled = validate_feature_vector(scaled_features)
        X_raw = validate_feature_vector(raw_features)

        h = horizon_minutes if horizon_minutes in self.HORIZONS else 15
        explainer = self.horizon_explainers.get(h)
        model = self.horizon_models.get(h)

        if not explainer or not model:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "horizon_minutes": h,
                "status": "EXPLANATION_UNAVAILABLE",
                "model_version": self.model_version,
                "schema_version": self.schema_version,
                "calibrated_probability": calibrated_probability,
                "raw_probability": raw_probability,
                "base_value": 0.0,
                "raw_margin": 0.0,
                "top_positive_contributors": [],
                "top_negative_contributors": [],
                "all_attributions": [],
                "additivity_verified": False,
                "additivity_delta": None,
                "computation_latency_ms": round(elapsed_ms, 3),
            }

        # 1. Compute exact TreeSHAP values
        raw_shap = explainer.shap_values(X_scaled)
        shap_vals = raw_shap[0] if isinstance(raw_shap, np.ndarray) and raw_shap.ndim == 2 else raw_shap

        # 2. Base value (expected margin) and raw margin (decision function output)
        base_val = explainer.expected_value
        if isinstance(base_val, (np.ndarray, list)):
            base_val = float(base_val[0])
        else:
            base_val = float(base_val)

        raw_margin = float(model.decision_function(X_scaled)[0])

        # 3. Additivity Verification: base_val + sum(shap) == raw_margin
        sum_shap = float(np.sum(shap_vals))
        additivity_delta = abs((base_val + sum_shap) - raw_margin)
        additivity_verified = bool(additivity_delta < 1e-4)

        # 4. Map SHAP values to feature definitions
        all_attributions: List[Dict[str, Any]] = []
        positive_list: List[Dict[str, Any]] = []
        negative_list: List[Dict[str, Any]] = []

        for idx, feat_def in enumerate(FEATURE_DEFINITIONS):
            observed_val = float(X_raw[0, idx])
            scaled_val = float(X_scaled[0, idx])
            sv = float(shap_vals[idx])

            direction = "increases_risk" if sv > 0 else "decreases_risk"
            desc = (
                feat_def.interpretation_template_positive
                if sv > 0
                else feat_def.interpretation_template_negative
            )

            attr_entry = {
                "feature_name": feat_def.name,
                "feature_index": idx,
                "observed_value": round(observed_val, 4),
                "scaled_value": round(scaled_val, 4),
                "unit": feat_def.unit,
                "source": feat_def.source,
                "shap_value": round(sv, 5),
                "absolute_magnitude": round(abs(sv), 5),
                "direction": direction,
                "description": desc,
                "feature_description": feat_def.description,
            }

            all_attributions.append(attr_entry)
            if sv > 1e-5:
                positive_list.append(attr_entry)
            elif sv < -1e-5:
                negative_list.append(attr_entry)

        # 5. Rank positive and negative contributors by magnitude
        positive_list.sort(key=lambda x: x["shap_value"], reverse=True)
        negative_list.sort(key=lambda x: x["shap_value"])  # Most negative first

        # Assign ranks
        for rank, item in enumerate(positive_list, 1):
            item["rank"] = rank
        for rank, item in enumerate(negative_list, 1):
            item["rank"] = rank

        top_pos = positive_list[:top_k]
        top_neg = negative_list[:top_k]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "horizon_minutes": h,
            "status": "EXPLAINED",
            "model_version": self.model_version,
            "schema_version": self.schema_version,
            "calibrated_probability": round(calibrated_probability, 4),
            "raw_probability": round(raw_probability, 4) if raw_probability is not None else None,
            "raw_margin": round(raw_margin, 5),
            "base_value": round(base_val, 5),
            "top_positive_contributors": top_pos,
            "top_negative_contributors": top_neg,
            "all_attributions": all_attributions,
            "additivity_verified": additivity_verified,
            "additivity_delta": round(additivity_delta, 8),
            "computation_latency_ms": round(elapsed_ms, 3),
        }

    def compute_global_feature_importance(
        self,
        X_scaled_val: np.ndarray,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Calculates global mean absolute SHAP feature importance on validation data."""
        X_val = validate_feature_vector(X_scaled_val)
        n_samples = len(X_val)

        horizon_importance: Dict[int, Dict[str, float]] = {}
        horizon_rankings: Dict[int, List[Dict[str, Any]]] = {}
        feature_names = get_feature_names()

        for h in self.HORIZONS:
            explainer = self.horizon_explainers.get(h)
            if not explainer:
                continue

            shap_matrix = explainer.shap_values(X_val)
            if isinstance(shap_matrix, list):
                shap_matrix = shap_matrix[0]

            mean_abs_shap = np.mean(np.abs(shap_matrix), axis=0)
            importance_map = {name: float(val) for name, val in zip(feature_names, mean_abs_shap)}
            horizon_importance[h] = importance_map

            ranked = sorted(
                [
                    {
                        "feature_name": name,
                        "feature_index": FEATURE_NAME_TO_INDEX[name],
                        "mean_abs_shap": round(importance_map[name], 5),
                        "unit": FEATURE_INDEX_TO_DEF[FEATURE_NAME_TO_INDEX[name]].unit,
                        "description": FEATURE_INDEX_TO_DEF[FEATURE_NAME_TO_INDEX[name]].description,
                    }
                    for name in feature_names
                ],
                key=lambda x: x["mean_abs_shap"],
                reverse=True,
            )
            for r, item in enumerate(ranked, 1):
                item["rank"] = r
            horizon_rankings[h] = ranked

        # Compute overall cross-horizon global importance
        overall_importance = {}
        for name in feature_names:
            overall_val = np.mean([horizon_importance[h][name] for h in self.HORIZONS if h in horizon_importance])
            overall_importance[name] = float(overall_val)

        top_global = sorted(
            [
                {
                    "feature_name": name,
                    "feature_index": FEATURE_NAME_TO_INDEX[name],
                    "mean_abs_shap": round(overall_importance[name], 5),
                    "unit": FEATURE_INDEX_TO_DEF[FEATURE_NAME_TO_INDEX[name]].unit,
                    "description": FEATURE_INDEX_TO_DEF[FEATURE_NAME_TO_INDEX[name]].description,
                }
                for name in feature_names
            ],
            key=lambda x: x["mean_abs_shap"],
            reverse=True,
        )[:top_n]

        for r, item in enumerate(top_global, 1):
            item["rank"] = r

        # Build 37x4 comparison matrix
        comparison_matrix: List[Dict[str, Any]] = []
        for idx, feat_def in enumerate(FEATURE_DEFINITIONS):
            name = feat_def.name
            row = {
                "feature_name": name,
                "feature_index": idx,
                "unit": feat_def.unit,
                "description": feat_def.description,
                "overall_mean_abs_shap": round(overall_importance.get(name, 0.0), 5),
                "shap_5m": round(horizon_importance.get(5, {}).get(name, 0.0), 5),
                "shap_15m": round(horizon_importance.get(15, {}).get(name, 0.0), 5),
                "shap_30m": round(horizon_importance.get(30, {}).get(name, 0.0), 5),
                "shap_60m": round(horizon_importance.get(60, {}).get(name, 0.0), 5),
            }
            comparison_matrix.append(row)

        comparison_matrix.sort(key=lambda x: x["overall_mean_abs_shap"], reverse=True)

        report = {
            "model_version": self.model_version,
            "schema_version": self.schema_version,
            "evaluated_samples_count": n_samples,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "top_global_features": top_global,
            "horizon_rankings": horizon_rankings,
            "horizon_comparison_matrix": comparison_matrix,
        }

        self.global_importance_cache = report
        return report

    def save_shap_artifacts(self, base_dir: str = "./artifacts") -> Dict[str, str]:
        """Persists SHAP explainer bundle and global importance report to disk."""
        shap_dir = os.path.join(base_dir, "shap")
        meta_dir = os.path.join(base_dir, "metadata")
        os.makedirs(shap_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)

        bundle_path = os.path.join(shap_dir, f"{self.model_version}_shap_explainers.joblib")
        joblib.dump(
            {
                "model_version": self.model_version,
                "schema_version": self.schema_version,
                "horizon_explainers": self.horizon_explainers,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
            bundle_path,
        )

        global_report_path = os.path.join(meta_dir, f"{self.model_version}_global_shap_report.json")
        if self.global_importance_cache:
            with open(global_report_path, "w", encoding="utf-8") as fh:
                json.dump(self.global_importance_cache, fh, indent=2)

        return {
            "shap_bundle": bundle_path,
            "global_report": global_report_path if self.global_importance_cache else "",
        }

    @classmethod
    def load_from_artifacts(
        cls,
        model_artifact_path: str = "./artifacts/models/v1.0.0-temporal-gbm.joblib",
        shap_artifact_path: str = "./artifacts/shap/v1.0.0-temporal-gbm_shap_explainers.joblib",
        model_version: str = "v1.0.0-temporal-gbm",
    ) -> "HorizonShapExplainer":
        """Loads SHAP explainers from disk or instantiates them from model bundle."""
        if os.path.exists(shap_artifact_path):
            try:
                bundle = joblib.load(shap_artifact_path)
                explainer_instance = cls(model_version=model_version)
                explainer_instance.horizon_explainers = bundle.get("horizon_explainers", {})
                explainer_instance.is_initialized = len(explainer_instance.horizon_explainers) > 0
                logger.info(f"Loaded SHAP explainers bundle from {shap_artifact_path}")
                return explainer_instance
            except Exception as e:
                logger.warning(f"Could not load SHAP bundle from {shap_artifact_path}: {e}")

        # Fallback to building from base models
        if os.path.exists(model_artifact_path):
            model_bundle = joblib.load(model_artifact_path)
            horizon_models = model_bundle.get("horizon_models", {})
            return cls(horizon_models=horizon_models, model_version=model_version)

        logger.warning("No model or SHAP artifact found. Initialized uncalibrated explainer standby.")
        return cls(model_version=model_version)
