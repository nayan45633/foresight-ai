"""Foresight AI - Risk State & Attack Path Forecasting REST API Endpoints (Step 7.1 Hardened).

Exposes deterministic risk evaluations and directed attack stage transition graphs grounded
in real network flow telemetry. Silent synthetic benchmark generation is completely removed
from production endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.models.telemetry import NetworkFlow
from app.db.session import get_db
from app.ml.contracts import (
    AttackPathForecast,
    FlowRecord,
    RiskStateEvaluation,
    RiskStateTransition,
    RiskTimelineResponse,
)
from app.ml.inference import ForecastingInferenceService
from app.ml.risk_engine import RiskStateEngine
from app.ml.train_pipeline import generate_benchmark_timeline
from app.telemetry.window_generator import SlidingWindowGenerator

router = APIRouter()

# Global singleton engine instance for persistent state & hysteresis across requests
_risk_engine: Optional[RiskStateEngine] = None
_inference_service: Optional[ForecastingInferenceService] = None


def get_inference_service() -> ForecastingInferenceService:
    global _inference_service
    if _inference_service is None:
        _inference_service = ForecastingInferenceService()
    return _inference_service


def get_risk_engine() -> RiskStateEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskStateEngine()
    return _risk_engine


async def _evaluate_current_pipeline_risk(db: AsyncSession) -> RiskStateEvaluation:
    """Helper that queries real database telemetry, generates windows, and evaluates risk engine."""
    svc = get_inference_service()
    engine = get_risk_engine()

    # Query real network flows from database (most recent 200 flows)
    stmt = select(NetworkFlow).order_by(NetworkFlow.timestamp.desc()).limit(200)
    result = await db.execute(stmt)
    db_flows = result.scalars().all()

    if not db_flows or len(db_flows) < 5:
        # Honest Empty State: Awaiting telemetry
        return engine.evaluate_empty_state()

    flow_records = [
        FlowRecord(
            id=f.id,
            timestamp=f.timestamp,
            source_ip=f.source_ip,
            destination_ip=f.destination_ip,
            source_port=f.source_port,
            destination_port=f.destination_port,
            protocol=f.protocol,
            flow_duration_ms=f.flow_duration_ms,
            packet_count=f.packet_count,
            byte_count=f.byte_count,
            packet_rate=f.packet_rate,
            byte_rate=f.byte_rate,
            tcp_flags=f.tcp_flags,
            connection_state=f.connection_state,
            direction=f.direction,
            metadata=f.metadata_payload,
        )
        for f in reversed(db_flows)
    ]

    win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
    windows = win_gen.generate_windows_from_flows(flow_records)

    if not windows:
        return engine.evaluate_empty_state()

    # Generate multi-horizon timeline from real windows
    timeline = svc.generate_forecast_timeline(window_sequence=windows[-20:])
    
    # Extract top SHAP explanations if available
    top_shap: List[dict] = []
    if timeline.horizons:
        first_h = timeline.horizons[0]
        top_shap = [f.model_dump() for f in first_h.shap_top_positive]

    evaluation = engine.evaluate_state(
        timeline=timeline,
        window=windows[-1] if windows else None,
        top_shap_features=top_shap,
    )
    return evaluation


@router.get(
    "/state",
    response_model=RiskStateEvaluation,
    summary="Get Current Risk State Evaluation",
    description="Returns the deterministic 5-tier security risk state evaluation with hysteresis details, signal evidence, and persistence counters based on real telemetry.",
)
async def get_current_risk_state(db: AsyncSession = Depends(get_db)) -> RiskStateEvaluation:
    try:
        return await _evaluate_current_pipeline_risk(db)
    except Exception as e:
        logger.error(f"Error evaluating current risk state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate risk state: {str(e)}",
        )


@router.get(
    "/attack-path",
    response_model=AttackPathForecast,
    summary="Get Attack Path Forecast Graph",
    description="Returns the directed attack stage transition graph predicting the next probable attack stage supported by telemetry and SHAP.",
)
async def get_attack_path_forecast(db: AsyncSession = Depends(get_db)) -> AttackPathForecast:
    try:
        evaluation = await _evaluate_current_pipeline_risk(db)
        if evaluation.attack_path_summary is None:
            engine = get_risk_engine()
            return engine.evaluate_empty_state().attack_path_summary or AttackPathForecast(
                forecast_id="apf-empty",
                target_entity="GLOBAL_PERIMETER",
                transition_confidence_status="AWAITING_TELEMETRY",
            )
        return evaluation.attack_path_summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating attack path forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate attack path: {str(e)}",
        )


@router.get(
    "/timeline",
    response_model=RiskTimelineResponse,
    summary="Get Chronological Risk State Timeline",
    description="Returns the chronological timeline of risk evaluations and auditable state transitions.",
)
async def get_risk_timeline(db: AsyncSession = Depends(get_db)) -> RiskTimelineResponse:
    try:
        await _evaluate_current_pipeline_risk(db)
        engine = get_risk_engine()
        return engine.get_timeline_response()
    except Exception as e:
        logger.error(f"Error retrieving risk timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve risk timeline: {str(e)}",
        )


@router.get(
    "/transitions",
    response_model=List[RiskStateTransition],
    summary="Get Auditable State Transitions",
    description="Returns the complete chronological audit log of security risk state transitions.",
)
async def get_risk_transitions(db: AsyncSession = Depends(get_db)) -> List[RiskStateTransition]:
    try:
        await _evaluate_current_pipeline_risk(db)
        engine = get_risk_engine()
        return list(reversed(engine.transition_history))
    except Exception as e:
        logger.error(f"Error retrieving risk transitions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve risk transitions: {str(e)}",
        )


@router.get(
    "/demo-state",
    response_model=RiskStateEvaluation,
    summary="Get Demo Risk State Evaluation (Explicit Demo Path)",
    description="Explicit demo endpoint that runs the risk engine against benchmark test telemetry for demonstration and verification purposes.",
)
async def get_demo_risk_state() -> RiskStateEvaluation:
    """Explicit demo endpoint that uses simulated benchmark telemetry."""
    try:
        svc = get_inference_service()
        engine = get_risk_engine()

        flows, gt = generate_benchmark_timeline(total_hours=2, flows_per_minute=25, random_seed=42)
        win_gen = SlidingWindowGenerator(window_size_seconds=60, stride_seconds=30)
        windows = win_gen.generate_windows_from_flows(flows)

        if not windows:
            return engine.evaluate_empty_state()

        timeline = svc.generate_forecast_timeline(window_sequence=windows[-20:])
        top_shap: List[dict] = []
        if timeline.horizons:
            top_shap = [f.model_dump() for f in timeline.horizons[0].shap_top_positive]

        evaluation = engine.evaluate_state(
            timeline=timeline,
            window=windows[-1] if windows else None,
            top_shap_features=top_shap,
        )
        return evaluation
    except Exception as e:
        logger.error(f"Error generating demo risk state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate demo risk state: {str(e)}",
        )
