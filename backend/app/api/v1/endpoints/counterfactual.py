"""Foresight AI - Counterfactual What-If REST Endpoints (Step 8).

Exposes model sensitivity analysis endpoints for interactive security simulation,
decision flip tracking, conformal set comparison, and TreeSHAP delta calculus.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import create_audit_entry, oauth2_scheme
from app.core.security import decode_access_token
from app.db.models.counterfactual import CounterfactualScenarioRecord
from app.db.models.user import User
from app.db.session import get_db
from app.ml.contracts import (
    CounterfactualPreset,
    CounterfactualScenarioRequest,
    CounterfactualScenarioResponse,
    FeatureMetadataCatalogResponse,
)
from app.ml.counterfactual import BUILTIN_PRESETS, counterfactual_engine
from app.ml.inference import inference_service

router = APIRouter()


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Helper retrieving authenticated user if token present, or None for guest/unauthenticated calls."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    res = await db.execute(select(User).where(User.id == payload["sub"]))
    return res.scalar_one_or_none()


@router.post("", response_model=CounterfactualScenarioResponse)
async def evaluate_counterfactual_scenario(
    payload: CounterfactualScenarioRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> CounterfactualScenarioResponse:
    """Executes full model re-inference on perturbed feature values.
    
    Quantifies probability shift (ΔP_h), decision flips, conformal prediction set transitions,
    and TreeSHAP attribution differentials across all horizons.
    """
    if not inference_service.is_ready and not inference_service._try_load():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecasting models and calibrators are not initialized or loaded.",
        )

    try:
        response = counterfactual_engine.evaluate_scenario(
            request=payload,
            inference_service=inference_service,
        )
        
        # Persist scenario to DB
        db_record = CounterfactualScenarioRecord(
            scenario_id=response.scenario_id,
            user_id=current_user.id if current_user else None,
            scenario_name=response.scenario_name,
            description=response.description,
            timestamp=response.timestamp,
            model_version=response.model_version,
            scientific_disclaimer=response.scientific_disclaimer,
            requested_perturbations=payload.perturbations,
            applied_perturbations=[p.model_dump() for p in response.applied_perturbations],
            horizon_results={k: v.model_dump() for k, v in response.horizon_results.items()},
            baseline_vector_summary=response.baseline_vector_summary,
            counterfactual_vector_summary=response.counterfactual_vector_summary,
            any_decision_flipped=response.any_decision_flipped,
            max_risk_reduction=response.max_risk_reduction,
            max_risk_elevation=response.max_risk_elevation,
            execution_latency_ms=response.execution_latency_ms,
            include_shap=payload.include_shap,
        )
        db.add(db_record)

        if current_user:
            await create_audit_entry(
                db=db,
                action="COUNTERFACTUAL_EVALUATED",
                resource_type="SCENARIO",
                resource_id=response.scenario_id,
                actor_user_id=current_user.id,
                actor_username=current_user.username,
                status="SUCCESS",
                details={"scenario_name": response.scenario_name, "flipped": response.any_decision_flipped},
            )
            
        await db.commit()
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Counterfactual simulation failed: {str(e)}",
        )


@router.get("/features", response_model=FeatureMetadataCatalogResponse)
async def get_counterfactual_features_catalog() -> FeatureMetadataCatalogResponse:
    """Returns metadata for all 37 schema features, allowable bounds, slider step sizes, and preset scenarios."""
    return counterfactual_engine.get_feature_catalog()


@router.get("/presets", response_model=List[CounterfactualPreset])
async def list_counterfactual_presets() -> List[CounterfactualPreset]:
    """Returns curated library of predefined security intervention and stress-testing scenario presets."""
    return BUILTIN_PRESETS


@router.get("/scenarios", response_model=List[CounterfactualScenarioResponse])
async def list_recent_scenarios(
    limit: int = Query(default=20, ge=1, le=100, description="Max scenario records to retrieve"),
) -> List[CounterfactualScenarioResponse]:
    """Retrieves chronological history of evaluated what-if simulation scenarios from in-memory audit log."""
    return counterfactual_engine.get_recent_scenarios(limit=limit)


@router.get("/scenario/{scenario_id}", response_model=CounterfactualScenarioResponse)
async def get_scenario_by_id(scenario_id: str) -> CounterfactualScenarioResponse:
    """Retrieves full comparative evaluation of an existing what-if scenario by its ID."""
    scenario = counterfactual_engine.get_scenario_by_id(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario with ID '{scenario_id}' not found in audit log.",
        )
    return scenario
