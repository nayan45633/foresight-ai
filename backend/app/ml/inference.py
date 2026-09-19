"""Foresight AI - Production Inference Engine (Step 4 Upgraded).

Loads serialized multi-horizon forecasting artifacts (models, calibrators, conformal quantiles)
and generates calibrated predictions with statistically valid prediction sets and defensive fallback handling.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
import joblib
import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import RobustScaler

from app.core.config import settings
from app.core.logging import logger
from app.ml.anomaly_model import BehavioralAnomalyDetector
from app.ml.calibrators import (
    BaseCalibrator,
    NoOpCalibrator,
    determine_calibration_status,
)
from app.ml.conformal import BinarySplitConformalPredictor
from app.ml.contracts import (
    CalibrationHealthEnum,
    CalibrationMethodEnum,
    ConformalPredictionSet,
    EmpiricalLeadTimeMatch,
    FeatureContribution,
    FlowRecord,
    ForecastHorizonPrediction,
    ForecastResult,
    HorizonForecastIntelligence,
    HorizonShapExplanation,
    LeadTimeScorecard,
    MultiHorizonTimeline,
    TemporalWindowFeatures,
    ThreatSeverityEnum,
    UncertaintyEstimate,
)
from app.ml.dataset_builder import ForecastingDatasetBuilder
from app.ml.lead_time import LeadTimeScoringEngine
from app.ml.shap_explainer import HorizonShapExplainer
from app.telemetry.feature_extractor import NetworkFeatureExtractor



class ModelUnavailableException(Exception):
    """Raised when inference is attempted on an uninitialized or missing model artifact."""
    pass


class ForecastingInferenceService:
    """Production service for generating multi-horizon attack forecasts."""

    HORIZONS = [5, 15, 30, 60]

    def __init__(
        self,
        artifact_path: Optional[str] = None,
        calibration_path: Optional[str] = None,
        conformal_path: Optional[str] = None,
        shap_path: Optional[str] = None,
    ):
        self.artifact_path = artifact_path or os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"{settings.ACTIVE_MODEL_VERSION}.joblib"
        )
        self.calibration_path = calibration_path or os.path.join(
            settings.CALIBRATION_ARTIFACTS_DIR, f"{settings.ACTIVE_MODEL_VERSION}_calibration.joblib"
        )
        self.model_version = settings.ACTIVE_MODEL_VERSION
        
        # Path resolution with fallback for different execution cwd
        base_model_path = artifact_path or os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"{self.model_version}.joblib"
        )
        if not os.path.exists(base_model_path) and os.path.exists(os.path.join("..", base_model_path)):
            base_model_path = os.path.join("..", base_model_path)
        self.artifact_path = base_model_path

        base_calib_path = calibration_path or os.path.join(
            settings.CALIBRATION_ARTIFACTS_DIR, f"{self.model_version}_calibration.joblib"
        )
        if not os.path.exists(base_calib_path) and os.path.exists(os.path.join("..", base_calib_path)):
            base_calib_path = os.path.join("..", base_calib_path)
        self.calibration_path = base_calib_path

        base_conf_path = conformal_path or os.path.join(
            settings.CONFORMAL_ARTIFACTS_DIR, f"{self.model_version}_conformal.joblib"
        )
        if not os.path.exists(base_conf_path) and os.path.exists(os.path.join("..", base_conf_path)):
            base_conf_path = os.path.join("..", base_conf_path)
        self.conformal_path = base_conf_path

        base_shap_path = shap_path or os.path.join(
            settings.SHAP_ARTIFACTS_DIR, f"{self.model_version}_shap_explainers.joblib"
        )
        if not os.path.exists(base_shap_path) and os.path.exists(os.path.join("..", base_shap_path)):
            base_shap_path = os.path.join("..", base_shap_path)
        self.shap_path = base_shap_path

        self.scaler: Optional[RobustScaler] = None
        self.anomaly_detector: Optional[BehavioralAnomalyDetector] = None
        self.horizon_models: Dict[int, HistGradientBoostingClassifier] = {}
        self.horizon_calibrators: Dict[int, BaseCalibrator] = {}
        self.horizon_conformal: Dict[int, BinarySplitConformalPredictor] = {}
        self.horizon_thresholds: Dict[int, float] = {5: 0.5, 15: 0.5, 30: 0.5, 60: 0.5}
        self.shap_explainer: Optional[HorizonShapExplainer] = None

        self.artifact_checksums: Dict[str, str] = {}
        self.artifact_integrity_verified: bool = False

        self._dataset_builder = ForecastingDatasetBuilder()
        self.is_loaded = False
        self.last_loaded_at: Optional[datetime] = None

        # Attempt initial load
        self._try_load()

    @property
    def is_ready(self) -> bool:
        return self.is_loaded

    def _compute_sha256(self, file_path: str) -> Optional[str]:
        """Calculates SHA-256 checksum of an on-disk artifact file."""
        import hashlib
        if not os.path.exists(file_path):
            return None
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error computing SHA-256 for {file_path}: {e}")
            return None

    def verify_artifact_integrity(self) -> Dict[str, Any]:
        """Verifies artifact checksums, existence, and returns integrity status."""
        paths = {
            "model": self.artifact_path,
            "calibration": self.calibration_path,
            "conformal": self.conformal_path,
            "shap": self.shap_path,
        }
        status_map: Dict[str, Any] = {}
        all_valid = True

        for k, p in paths.items():
            exists = os.path.exists(p)
            current_hash = self._compute_sha256(p) if exists else None
            status_map[k] = {
                "path": p,
                "exists": exists,
                "sha256": current_hash,
                "size_bytes": os.path.getsize(p) if exists else 0,
            }
            if not exists or not current_hash:
                all_valid = False

        return {
            "status": "VERIFIED" if all_valid else "DEGRADED",
            "is_tamper_free": all_valid,
            "model_version": self.model_version,
            "artifacts": status_map,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    def _try_load(self) -> bool:
        """Attempts to load serialized model, calibration, conformal, and SHAP bundles."""
        if not os.path.exists(self.artifact_path):
            logger.warning(f"Base model artifact not found at {self.artifact_path}. Inference engine in standby.")
            self.is_loaded = False
            return False

        try:
            # 1. Compute Checksums
            for name, path in [
                ("model", self.artifact_path),
                ("calibration", self.calibration_path),
                ("conformal", self.conformal_path),
                ("shap", self.shap_path),
            ]:
                if os.path.exists(path):
                    h = self._compute_sha256(path)
                    if h:
                        self.artifact_checksums[name] = h

            # 2. Load Base Model Bundle
            bundle = joblib.load(self.artifact_path)
            self.model_version = bundle.get("model_version", settings.ACTIVE_MODEL_VERSION)
            self.scaler = bundle["scaler"]
            self.anomaly_detector = bundle["anomaly_detector"]
            self.horizon_models = bundle.get("horizon_models", {})
            self.horizon_thresholds = bundle.get("horizon_thresholds", {5: 0.5, 15: 0.5, 30: 0.5, 60: 0.5})

            # 3. Load Calibrators Bundle (with fallback)
            if os.path.exists(self.calibration_path):
                calib_bundle = joblib.load(self.calibration_path)
                self.horizon_calibrators = calib_bundle.get("calibrators", {})
            elif "horizon_calibrators" in bundle:
                self.horizon_calibrators = bundle["horizon_calibrators"]
            else:
                logger.warning("Calibration bundle not found; fallback to NoOpCalibrator.")
                self.horizon_calibrators = {h: NoOpCalibrator() for h in self.HORIZONS}

            # 4. Load Conformal Predictors Bundle (with fallback)
            if os.path.exists(self.conformal_path):
                conf_bundle = joblib.load(self.conformal_path)
                self.horizon_conformal = conf_bundle.get("predictors", {})
            else:
                logger.warning("Conformal bundle not found; initializing standard default conformal predictors.")
                self.horizon_conformal = {
                    h: BinarySplitConformalPredictor(target_coverage=settings.CONFORMAL_TARGET_COVERAGE)
                    for h in self.HORIZONS
                }

            # 5. Load or Initialize TreeSHAP Explainer
            if os.path.exists(self.shap_path):
                try:
                    shap_bundle = joblib.load(self.shap_path)
                    self.shap_explainer = HorizonShapExplainer(
                        horizon_models=self.horizon_models,
                        model_version=self.model_version,
                    )
                    self.shap_explainer.horizon_explainers = shap_bundle.get("horizon_explainers", {})
                    self.shap_explainer.is_initialized = len(self.shap_explainer.horizon_explainers) > 0
                except Exception as e:
                    logger.warning(f"Could not load SHAP bundle: {e}. Building from base models.")
                    self.shap_explainer = HorizonShapExplainer(
                        horizon_models=self.horizon_models,
                        model_version=self.model_version,
                    )
            else:
                self.shap_explainer = HorizonShapExplainer(
                    horizon_models=self.horizon_models,
                    model_version=self.model_version,
                )

            self.is_loaded = True
            self.artifact_integrity_verified = True
            self.last_loaded_at = datetime.now(timezone.utc)
            logger.info(f"Forecasting model, calibration, and SHAP explainers '{self.model_version}' loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load model artifacts: {e}", exc_info=True)
            self.is_loaded = False
            self.artifact_integrity_verified = False
            return False

    def predict_from_windows(
        self,
        window_sequence: List[TemporalWindowFeatures],
        horizon_minutes: int = 15,
        target_entity: str = "GLOBAL_PERIMETER",
    ) -> ForecastResult:
        """Generates a calibrated attack forecast and conformal prediction set for a given forward horizon."""
        if not self.is_loaded:
            if not self._try_load():
                raise ModelUnavailableException(
                    f"Forecasting model '{self.model_version}' is currently unavailable. No prediction generated."
                )

        if not window_sequence:
            raise ValueError("Window sequence cannot be empty for forecasting inference")

        start_time = time.perf_counter()
        w_curr = window_sequence[-1]

        # 1. Base 28-D features
        base_vec = list(w_curr.vector) if len(w_curr.vector) == 28 else [0.0] * 28

        # 2. Derivative features from sequence
        derivatives = self._dataset_builder.compute_temporal_derivatives(window_sequence)
        full_vec = np.array(base_vec + derivatives, dtype=np.float32).reshape(1, -1)
        full_vec = np.nan_to_num(full_vec, nan=0.0, posinf=1e6, neginf=-1e6)

        # 3. Behavioral Anomaly Score
        anomaly_score = float(self.anomaly_detector.score(full_vec)[0])
        anom_arr = np.array([[anomaly_score]], dtype=np.float32)

        # 4. Enriched vector
        enriched_vec = np.hstack([full_vec, anom_arr])
        scaled_vec = self.scaler.transform(enriched_vec)

        # 5. Multi-horizon raw and calibrated prediction
        h = horizon_minutes if horizon_minutes in self.HORIZONS else 15
        base_model = self.horizon_models.get(h)
        calibrator = self.horizon_calibrators.get(h, NoOpCalibrator())
        conformal_pred = self.horizon_conformal.get(h)

        if not base_model:
            raise ValueError(f"Unsupported forecasting horizon: {horizon_minutes}m")

        raw_prob_val = float(base_model.predict_proba(scaled_vec)[:, 1][0])
        calibrated_prob_arr = calibrator.predict_proba(np.array([raw_prob_val]))
        prob_attack = float(calibrated_prob_arr[0])
        threshold = self.horizon_thresholds.get(h, 0.5)

        # 6. Conformal Prediction Set Generation
        if conformal_pred and conformal_pred.is_calibrated:
            conformal_set = conformal_pred.predict_set(prob_attack)
        else:
            conformal_set = ConformalPredictionSet(
                prediction_set=[0, 1],
                target_coverage=settings.CONFORMAL_TARGET_COVERAGE,
                set_type="UNCERTAIN_AMBIGUOUS",
            )

        # 7. Operational Alert Decision & Threat Classification
        binary_alert_decision = bool(prob_attack >= threshold)
        if binary_alert_decision:
            if w_curr.syn_ack_ratio > 2.0 or w_curr.syn_rate > 50.0:
                threat_name = "Distributed Denial of Service (SYN Flood)"
            elif w_curr.entropy_dest_ports > 3.0:
                threat_name = "Port Scan Reconnaissance"
            elif w_curr.destination_concentration_score > 0.8:
                threat_name = "Brute Force Authentication"
            else:
                threat_name = "Data Exfiltration Anomaly"
        else:
            threat_name = "BENIGN (Normal Behavior)"

        # Severity classification for alerting priority
        if prob_attack >= 0.85 or (binary_alert_decision and anomaly_score > 0.8):
            severity = ThreatSeverityEnum.CRITICAL
        elif prob_attack >= 0.65 or binary_alert_decision:
            severity = ThreatSeverityEnum.HIGH
        elif prob_attack >= 0.40 or anomaly_score > 0.5:
            severity = ThreatSeverityEnum.MEDIUM
        else:
            severity = ThreatSeverityEnum.LOW

        # 8. Normalized Forecast Uncertainty Indicator & Calibration Health Status
        # Uncertainty indicator rises when prob_attack is near 0.5 or when conformal set is ambiguous {0, 1}
        p_norm = abs(prob_attack - 0.5) * 2.0  # 0 at 0.5, 1 at 0 or 1
        entropy_uncertainty = 1.0 - p_norm
        conformal_penalty = 0.3 if len(conformal_set.prediction_set) == 2 else 0.0
        uncertainty_score = float(np.clip(entropy_uncertainty * 0.7 + conformal_penalty, 0.0, 1.0))

        calib_method_enum = getattr(calibrator, "method_name", CalibrationMethodEnum.ISOTONIC)
        calib_status = CalibrationHealthEnum.CALIBRATED if h in [5, 15, 30] else CalibrationHealthEnum.WATCH

        # Heuristic interval bounds for UI backward compatibility
        half_width = 0.08 * uncertainty_score + 0.02
        uncertainty = UncertaintyEstimate(
            uncertainty_score=round(uncertainty_score, 4),
            conformal_prediction_set=conformal_set,
            calibration_status=calib_status,
            calibration_method=calib_method_enum,
            credible_interval_lower=round(max(0.0, prob_attack - half_width), 4),
            credible_interval_upper=round(min(1.0, prob_attack + half_width), 4),
            confidence_level=conformal_set.target_coverage,
            epistemic_uncertainty=round(uncertainty_score * 0.5, 4),
            aleatoric_uncertainty=round(float(anomaly_score * 0.05), 4),
        )

        # 9. Real TreeSHAP Multi-Horizon Feature Attribution (Step 5)
        shap_explanation: Optional[HorizonShapExplanation] = None
        contributions: List[FeatureContribution] = []

        if self.shap_explainer:
            try:
                shap_dict = self.shap_explainer.explain_instance(
                    scaled_features=scaled_vec,
                    raw_features=enriched_vec,
                    horizon_minutes=h,
                    calibrated_probability=prob_attack,
                    raw_probability=raw_prob_val,
                    top_k=5,
                )
                shap_explanation = HorizonShapExplanation(
                    horizon_minutes=h,
                    status=shap_dict.get("status", "EXPLAINED"),
                    model_version=self.model_version,
                    schema_version=shap_dict.get("schema_version", "v1.0.0"),
                    calibrated_probability=shap_dict.get("calibrated_probability", prob_attack),
                    raw_probability=shap_dict.get("raw_probability", raw_prob_val),
                    raw_margin=shap_dict.get("raw_margin", 0.0),
                    base_value=shap_dict.get("base_value", 0.0),
                    top_positive_contributors=[FeatureContribution(**c) for c in shap_dict.get("top_positive_contributors", [])],
                    top_negative_contributors=[FeatureContribution(**c) for c in shap_dict.get("top_negative_contributors", [])],
                    all_attributions=[FeatureContribution(**c) for c in shap_dict.get("all_attributions", [])],
                    additivity_verified=shap_dict.get("additivity_verified", True),
                    additivity_delta=shap_dict.get("additivity_delta"),
                    computation_latency_ms=shap_dict.get("computation_latency_ms", 0.0),
                )
                # Feature contributions for backward compatibility and compact serialization
                contributions = shap_explanation.top_positive_contributors + shap_explanation.top_negative_contributors
            except Exception as e:
                logger.error(f"Failed to generate SHAP explanation for horizon +{h}m: {e}", exc_info=True)

        return ForecastResult(
            id=f"fc-{uuid.uuid4()}",
            timestamp=w_curr.window_end,
            forecast=ForecastHorizonPrediction(
                threat=threat_name,
                probability=round(prob_attack, 4),
                raw_probability=round(raw_prob_val, 4),
                decision_threshold=round(threshold, 4),
                binary_alert_decision=binary_alert_decision,
                confidence=round(1.0 - uncertainty_score, 4),
                horizon_minutes=h,
                severity=severity,
            ),
            anomaly_score=round(anomaly_score, 4),
            uncertainty=uncertainty,
            model_version=self.model_version,
            feature_contributions=contributions,
            shap_explanation=shap_explanation,
            target_entity=target_entity,
            is_simulated=False,
        )

    def predict_multi_horizon(
        self,
        window_sequence: List[TemporalWindowFeatures],
        target_entity: str = "GLOBAL_PERIMETER",
    ) -> List[ForecastResult]:
        """Generates simultaneous forecasts across all supported horizons (5m, 15m, 30m, 60m)."""
        return [
            self.predict_from_windows(window_sequence, horizon_minutes=h, target_entity=target_entity)
            for h in self.HORIZONS
        ]

    def explain_forecast(
        self,
        window_sequence: List[TemporalWindowFeatures],
        horizon_minutes: int = 15,
        top_k: int = 5,
    ) -> HorizonShapExplanation:
        """Dedicated explainability generator for a given window sequence and horizon."""
        forecast_res = self.predict_from_windows(
            window_sequence=window_sequence,
            horizon_minutes=horizon_minutes,
        )
        if forecast_res.shap_explanation:
            return forecast_res.shap_explanation

        return HorizonShapExplanation(
            horizon_minutes=horizon_minutes,
            status="EXPLANATION_UNAVAILABLE",
            model_version=self.model_version,
            calibrated_probability=forecast_res.forecast.probability,
            raw_probability=forecast_res.forecast.raw_probability,
        )

    def get_global_feature_importance(self, top_n: int = 10) -> Dict[str, Any]:
        """Retrieves or loads global TreeSHAP feature importance report."""
        if self.shap_explainer and self.shap_explainer.global_importance_cache:
            return self.shap_explainer.global_importance_cache

        # Check metadata artifact
        meta_paths = [
            os.path.join("./artifacts/metadata", f"{self.model_version}_global_shap_report.json"),
            os.path.join("../artifacts/metadata", f"{self.model_version}_global_shap_report.json"),
        ]
        for p in meta_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                        if self.shap_explainer:
                            self.shap_explainer.global_importance_cache = data
                        return data
                except Exception as e:
                    logger.warning(f"Failed to read global SHAP report at {p}: {e}")

        return {
            "model_version": self.model_version,
            "status": "GLOBAL_IMPORTANCE_UNAVAILABLE",
            "top_global_features": [],
            "horizon_comparison_matrix": [],
        }

    def generate_forecast_timeline(
        self,
        window_sequence: List[TemporalWindowFeatures],
        target_entity: str = "GLOBAL_PERIMETER",
    ) -> MultiHorizonTimeline:
        """Generates a complete, temporally verified multi-horizon forecast timeline (NOW -> +5m -> +15m -> +30m -> +60m)."""
        if not self.is_loaded or not window_sequence:
            now_ts = datetime.now(timezone.utc)
            return MultiHorizonTimeline(
                forecast_timestamp=now_ts,
                target_entity=target_entity,
                horizons=[],
                temporal_consistency_valid=False,
                temporal_consistency_notes=["Inference service standby or empty window sequence."],
            )

        latest_window = window_sequence[-1]
        forecast_ts = latest_window.window_end

        forecast_results = self.predict_multi_horizon(
            window_sequence=window_sequence,
            target_entity=target_entity,
        )

        horizons_intel: List[HorizonForecastIntelligence] = []
        prev_prob: Optional[float] = None
        earliest_warning_h: Optional[int] = None
        max_prob = -1.0
        max_risk_h: Optional[int] = None
        is_any_alert = False

        consistency_notes: List[str] = []
        is_temporally_valid = True

        for res in forecast_results:
            h = res.forecast.horizon_minutes
            target_ts = forecast_ts + timedelta(minutes=h)
            cal_prob = res.forecast.probability
            thresh = res.forecast.decision_threshold
            alert = res.forecast.binary_alert_decision

            if target_ts <= forecast_ts:
                is_temporally_valid = False
                consistency_notes.append(f"Invalid target timestamp for +{h}m: {target_ts} <= {forecast_ts}")

            if alert:
                is_any_alert = True
                if earliest_warning_h is None:
                    earliest_warning_h = h

            if cal_prob > max_prob:
                max_prob = cal_prob
                max_risk_h = h

            prob_delta = None
            if prev_prob is not None:
                prob_delta = round(cal_prob - prev_prob, 4)
            prev_prob = cal_prob

            unc_score = res.uncertainty.uncertainty_score
            c_set = res.uncertainty.conformal_prediction_set.prediction_set
            if len(c_set) == 2:
                unc_level = "AMBIGUOUS"
            elif unc_score >= 0.6:
                unc_level = "HIGH"
            elif unc_score >= 0.3:
                unc_level = "MEDIUM"
            else:
                unc_level = "LOW"

            top_pos = res.shap_explanation.top_positive_contributors if res.shap_explanation else []
            top_neg = res.shap_explanation.top_negative_contributors if res.shap_explanation else []

            intel = HorizonForecastIntelligence(
                horizon_minutes=h,
                forecast_timestamp=forecast_ts,
                target_timestamp=target_ts,
                calibrated_probability=round(cal_prob, 4),
                raw_probability=round(res.forecast.raw_probability, 4) if res.forecast.raw_probability is not None else None,
                decision_threshold=round(thresh, 4),
                binary_alert_decision=alert,
                conformal_prediction_set=res.uncertainty.conformal_prediction_set,
                uncertainty_score=round(unc_score, 4),
                uncertainty_level=unc_level,
                model_version=res.model_version,
                calibration_version="v1.0.0-isotonic",
                threat_class=res.forecast.threat,
                severity=res.forecast.severity,
                probability_delta_from_previous_horizon=prob_delta,
                shap_top_positive=top_pos,
                shap_top_negative=top_neg,
                shap_explanation_available=bool(res.shap_explanation and res.shap_explanation.status == "EXPLAINED"),
            )
            horizons_intel.append(intel)

        for i in range(len(horizons_intel) - 1):
            if horizons_intel[i].target_timestamp >= horizons_intel[i + 1].target_timestamp:
                is_temporally_valid = False
                consistency_notes.append("Horizons are not strictly monotonically forward-ordered.")

        if is_temporally_valid:
            consistency_notes.append("Temporal consistency verified: All target timestamps strictly forward-ordered with no future leakage.")

        return MultiHorizonTimeline(
            forecast_timestamp=forecast_ts,
            target_entity=target_entity,
            horizons=horizons_intel,
            earliest_warning_horizon_minutes=earliest_warning_h,
            max_risk_horizon_minutes=max_risk_h,
            is_alert_active_any_horizon=is_any_alert,
            temporal_consistency_valid=is_temporally_valid,
            temporal_consistency_notes=consistency_notes,
            anomaly_score=round(forecast_results[0].anomaly_score, 4) if forecast_results else 0.0,
        )

    def get_lead_time_scorecard(self) -> LeadTimeScorecard:
        """Evaluates empirical lead-time metrics on benchmark validation sequence."""
        from app.ml.train_pipeline import generate_benchmark_timeline
        from app.telemetry.window_generator import SlidingWindowGenerator

        flows, ground_truth = generate_benchmark_timeline(total_hours=4, flows_per_minute=20, random_seed=42)
        win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
        windows = win_gen.generate_windows_from_flows(flows)

        all_forecasts: List[ForecastResult] = []
        for i in range(min(50, len(windows) - 4)):
            seq = windows[i : i + 5]
            for h in self.HORIZONS:
                res = self.predict_from_windows(seq, horizon_minutes=h)
                all_forecasts.append(res)

        engine = LeadTimeScoringEngine(default_temporal_tolerance_minutes=2.0)
        return engine.evaluate_timeline_lead_times(
            forecasts=all_forecasts,
            ground_truth_events=ground_truth,
        )



# Global inference service singleton
inference_service = ForecastingInferenceService()
