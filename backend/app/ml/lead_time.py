"""Foresight AI - Empirical Forecast Lead-Time Scoring & Deterministic Event Matching Engine (Step 6).

Quantifies how far in advance Foresight AI forecasts an attack before it actually occurs:
    empirical_lead_time_minutes = actual_attack_timestamp - forecast_timestamp

Implements a deterministic, chronological event matching policy:
1. Valid Forecast Alert: Emitted at T_forecast with calibrated_probability >= decision_threshold.
2. Temporal Window: Matches a ground truth attack at T_event iff:
       T_forecast < T_event <= T_forecast + timedelta(minutes=horizon_minutes + temporal_tolerance)
3. First-Warning Tracking: The earliest valid forecast for each attack event defines its primary lead time.
4. Double-Counting Prevention: Each ground-truth attack event is matched to its earliest distinct warning.
5. Strict Empirical Discipline: No fabricated lead times; explicitly returns INSUFFICIENT_EMPIRICAL_MATCHES
   when insufficient ground truth events are present.
"""

from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.ml.contracts import (
    EmpiricalLeadTimeMatch,
    ForecastResult,
    LeadTimeScorecard,
)


class LeadTimeRecord(BaseModel):
    """Legacy record for single forecast evaluation (preserved for backward compatibility)."""
    forecast_id: str
    target_entity: str
    predicted_threat: str
    forecast_timestamp: datetime
    horizon_minutes: int
    forecast_probability: float
    actual_event_timestamp: Optional[datetime] = None
    actual_threat: Optional[str] = None
    lead_time_minutes: Optional[float] = None
    is_valid_early_warning: bool = False

    model_config = ConfigDict(from_attributes=True)


class LeadTimeScoringEngine:
    """Deterministic, chronological empirical lead-time scoring and event matching engine."""

    def __init__(
        self,
        probability_threshold: float = 0.5,
        default_temporal_tolerance_minutes: float = 2.0,
    ):
        self.probability_threshold = probability_threshold
        self.temporal_tolerance_minutes = default_temporal_tolerance_minutes

    def match_forecast_to_attack(
        self,
        forecast: ForecastResult,
        ground_truth_events: List[Dict[str, Any]],
    ) -> LeadTimeRecord:
        """Evaluates whether a single forecast provided a valid early-warning before an attack event."""
        forecast_ts = forecast.timestamp
        horizon_m = forecast.forecast.horizon_minutes
        prob = forecast.forecast.probability
        thresh = forecast.forecast.decision_threshold or self.probability_threshold
        predicted_threat = forecast.forecast.threat

        # Candidate future window for this forecast
        horizon_end = forecast_ts + timedelta(minutes=horizon_m + self.temporal_tolerance_minutes)

        matching_event = None
        for ev in ground_truth_events:
            ev_ts = ev["timestamp"]
            threat_type = ev.get("threat_type", "BENIGN")
            # Must occur strictly after forecast and within horizon window
            if forecast_ts < ev_ts <= horizon_end and threat_type != "BENIGN":
                matching_event = ev
                break

        is_alert = bool(forecast.forecast.binary_alert_decision or prob >= thresh)
        if matching_event and is_alert:
            actual_ts = matching_event["timestamp"]
            lead_time_min = (actual_ts - forecast_ts).total_seconds() / 60.0
            return LeadTimeRecord(
                forecast_id=forecast.id,
                target_entity=forecast.target_entity,
                predicted_threat=predicted_threat,
                forecast_timestamp=forecast_ts,
                horizon_minutes=horizon_m,
                forecast_probability=prob,
                actual_event_timestamp=actual_ts,
                actual_threat=matching_event.get("threat_type"),
                lead_time_minutes=round(lead_time_min, 2),
                is_valid_early_warning=True,
            )

        return LeadTimeRecord(
            forecast_id=forecast.id,
            target_entity=forecast.target_entity,
            predicted_threat=predicted_threat,
            forecast_timestamp=forecast_ts,
            horizon_minutes=horizon_m,
            forecast_probability=prob,
            actual_event_timestamp=matching_event["timestamp"] if matching_event else None,
            actual_threat=matching_event.get("threat_type") if matching_event else None,
            lead_time_minutes=None,
            is_valid_early_warning=False,
        )

    def evaluate_timeline_lead_times(
        self,
        forecasts: List[ForecastResult],
        ground_truth_events: List[Dict[str, Any]],
        temporal_tolerance_minutes: Optional[float] = None,
    ) -> LeadTimeScorecard:
        """Deterministically matches an entire timeline of forecasts against ground-truth attack events.
        
        Enforces:
        - Chronological processing (forecast_ts < actual_attack_ts).
        - Multi-horizon evaluation (+5m, +15m, +30m, +60m).
        - First valid warning per event tracking to prevent double-counting.
        - Strict empirical computation of mean, median, min, max, std lead times.
        - Fail-safe handling for zero/insufficient matches.
        """
        tol_min = temporal_tolerance_minutes if temporal_tolerance_minutes is not None else self.temporal_tolerance_minutes

        # Filter and sort genuine attack events chronologically
        attack_events = [
            e for e in ground_truth_events
            if e.get("threat_type", "BENIGN") != "BENIGN" and e.get("attack_occurred", True)
        ]
        attack_events.sort(key=lambda x: x["timestamp"])

        # Sort forecasts chronologically
        sorted_forecasts = sorted(forecasts, key=lambda f: f.timestamp)

        if not attack_events or not sorted_forecasts:
            return LeadTimeScorecard(
                status="INSUFFICIENT_EMPIRICAL_MATCHES",
                status_message="Awaiting matched attack events (no ground-truth events or forecasts available).",
                total_emitted_forecasts=len(sorted_forecasts),
                total_attack_events=len(attack_events),
                valid_forecast_event_matches=0,
                missed_attack_events=len(attack_events),
                false_early_warnings=0,
                unmatched_forecasts=0,
            )

        # Tracking state
        event_matched_earliest_alert: Dict[str, EmpiricalLeadTimeMatch] = {}
        all_valid_matches: List[EmpiricalLeadTimeMatch] = []
        forecast_matched_event_ids: set = set()
        matched_event_ids: set = set()
        horizon_dist: Dict[str, int] = {"5m": 0, "15m": 0, "30m": 0, "60m": 0}

        # Match each active forecast alert to applicable ground-truth events
        for fc in sorted_forecasts:
            is_alert = fc.forecast.binary_alert_decision or (fc.forecast.probability >= fc.forecast.decision_threshold)
            if not is_alert:
                continue

            fc_ts = fc.timestamp
            h_min = fc.forecast.horizon_minutes
            window_end = fc_ts + timedelta(minutes=h_min + tol_min)

            # Find matching events in [fc_ts, window_end]
            for idx, ev in enumerate(attack_events):
                ev_ts = ev["timestamp"]
                ev_id = ev.get("id") or ev.get("event_id") or f"ev_{idx}_{ev_ts.isoformat()}"

                if fc_ts < ev_ts <= window_end:
                    lead_min = round((ev_ts - fc_ts).total_seconds() / 60.0, 2)
                    match_record = EmpiricalLeadTimeMatch(
                        match_id=f"match_{uuid.uuid4().hex[:8]}",
                        forecast_id=fc.id,
                        forecast_timestamp=fc_ts,
                        horizon_minutes=h_min,
                        forecast_probability=round(fc.forecast.probability, 4),
                        decision_threshold=round(fc.forecast.decision_threshold, 4),
                        actual_event_id=ev_id,
                        actual_event_timestamp=ev_ts,
                        actual_threat_type=ev.get("threat_type", "MALICIOUS_ATTACK"),
                        empirical_lead_time_minutes=lead_min,
                        is_earliest_warning_for_event=False,
                    )
                    all_valid_matches.append(match_record)
                    forecast_matched_event_ids.add(fc.id)
                    matched_event_ids.add(ev_id)

                    # Update earliest warning for this event if not present or earlier
                    if ev_id not in event_matched_earliest_alert:
                        match_record.is_earliest_warning_for_event = True
                        event_matched_earliest_alert[ev_id] = match_record
                    else:
                        existing_earliest = event_matched_earliest_alert[ev_id]
                        if match_record.empirical_lead_time_minutes > existing_earliest.empirical_lead_time_minutes:
                            existing_earliest.is_earliest_warning_for_event = False
                            match_record.is_earliest_warning_for_event = True
                            event_matched_earliest_alert[ev_id] = match_record

        # Collect distinct earliest lead times for metric computation
        earliest_lead_times = [m.empirical_lead_time_minutes for m in event_matched_earliest_alert.values()]

        # Compute horizon distribution of earliest warnings
        for m in event_matched_earliest_alert.values():
            h_key = f"{m.horizon_minutes}m"
            horizon_dist[h_key] = horizon_dist.get(h_key, 0) + 1

        total_alerts = sum(
            1 for fc in sorted_forecasts
            if fc.forecast.binary_alert_decision or (fc.forecast.probability >= fc.forecast.decision_threshold)
        )
        false_warnings = total_alerts - len(forecast_matched_event_ids)
        missed_events = len(attack_events) - len(matched_event_ids)

        if not earliest_lead_times:
            return LeadTimeScorecard(
                evaluation_period_start=sorted_forecasts[0].timestamp,
                evaluation_period_end=sorted_forecasts[-1].timestamp,
                status="INSUFFICIENT_EMPIRICAL_MATCHES",
                status_message="Awaiting matched attack events (no valid forecast alerts matched ground-truth attacks).",
                total_emitted_forecasts=len(sorted_forecasts),
                total_attack_events=len(attack_events),
                valid_forecast_event_matches=0,
                missed_attack_events=missed_events,
                false_early_warnings=false_warnings,
                unmatched_forecasts=false_warnings,
                empirical_forecast_coverage_rate=0.0,
                earliest_warning_horizon_distribution=horizon_dist,
                matches=[],
            )

        mean_lead = round(float(np.mean(earliest_lead_times)), 2)
        median_lead = round(float(np.median(earliest_lead_times)), 2)
        min_lead = round(float(np.min(earliest_lead_times)), 2)
        max_lead = round(float(np.max(earliest_lead_times)), 2)
        std_lead = round(float(np.std(earliest_lead_times)), 2)
        coverage_rate = round(len(matched_event_ids) / len(attack_events), 4) if attack_events else 0.0

        return LeadTimeScorecard(
            evaluation_period_start=sorted_forecasts[0].timestamp,
            evaluation_period_end=sorted_forecasts[-1].timestamp,
            status="EMPIRICALLY_EVALUATED",
            status_message=f"Empirical lead-time metrics verified across {len(matched_event_ids)} matched attack events.",
            mean_lead_time_minutes=mean_lead,
            median_lead_time_minutes=median_lead,
            min_lead_time_minutes=min_lead,
            max_lead_time_minutes=max_lead,
            std_lead_time_minutes=std_lead,
            total_emitted_forecasts=len(sorted_forecasts),
            total_attack_events=len(attack_events),
            valid_forecast_event_matches=len(matched_event_ids),
            missed_attack_events=missed_events,
            false_early_warnings=max(0, false_warnings),
            unmatched_forecasts=max(0, false_warnings),
            empirical_forecast_coverage_rate=coverage_rate,
            earliest_warning_horizon_distribution=horizon_dist,
            matches=all_valid_matches[:50],  # Return up to 50 detailed matches
        )
