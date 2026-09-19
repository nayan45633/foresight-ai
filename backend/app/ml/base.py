"""Foresight AI - Abstract Machine Learning & Pipeline Interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.ml.contracts import (
    FeatureContribution,
    FlowRecord,
    ForecastResult,
    TemporalWindowFeatures,
    UncertaintyEstimate,
)


class BaseTelemetryNormalizer(ABC):
    """Abstract normalizer converting raw heterogeneous network feeds into FlowRecord."""
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> FlowRecord:
        """Transforms a raw telemetry dictionary into a typed FlowRecord."""
        pass

    @abstractmethod
    def batch_normalize(self, raw_records: List[Dict[str, Any]]) -> List[FlowRecord]:
        """Transforms a batch of raw records."""
        pass


class BaseFeatureExtractor(ABC):
    """Abstract feature extractor computing temporal window statistics."""
    
    @abstractmethod
    def extract_window_features(
        self, flows: List[FlowRecord], window_duration_seconds: int = 60
    ) -> TemporalWindowFeatures:
        """Transforms an array of flows into aggregated statistical features."""
        pass


class BaseForecastingModel(ABC):
    """Abstract model interface for temporal attack forecasting."""
    
    @abstractmethod
    def load(self, model_path: str) -> None:
        """Loads model weights/artifacts from disk."""
        pass

    @abstractmethod
    def predict_forecast(
        self,
        features: TemporalWindowFeatures,
        horizon_minutes: int = 15
    ) -> ForecastResult:
        """Generates a calibrated attack forecast from temporal features."""
        pass

    @abstractmethod
    def estimate_uncertainty(self, features: TemporalWindowFeatures) -> UncertaintyEstimate:
        """Quantifies predictive uncertainty."""
        pass


class BaseExplainabilityEngine(ABC):
    """Abstract engine for extracting feature attributions (SHAP / Integrated Gradients)."""
    
    @abstractmethod
    def explain(
        self, model: Any, features: TemporalWindowFeatures
    ) -> List[FeatureContribution]:
        """Calculates feature importance values for the prediction."""
        pass
