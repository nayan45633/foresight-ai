# Empirical Lead-Time Measurement Methodology

## 1. Core Principle: Empirical vs Theoretical Lead Time

A common error in forecasting systems is equating theoretical lookahead horizon (e.g., 'this is a 60-minute model, so it gives 60 minutes of lead time') with empirical operational lead time.

In Foresight AI:
- **Theoretical Horizon (H)**: The forward target window over which the model is trained to predict whether an attack begins within t + H.
- **Empirical Lead Time (Delta T_lead)**: The actual measured elapsed time between the *first statistically validated alert* and the actual timestamp of the ground-truth attack event.

---

## 2. Chronological Event-Matching Discipline

Foresight AI implements a strictly causal, chronological matching policy via LeadTimeScoringEngine:

### 2.1 Forward Causal Requirement
For any attack event E_j occurring at T_{event, j} and a positive forecast alert F_i emitted at T_{forecast, i} for horizon H_i:
1. The forecast MUST strictly precede the event:
   T_{forecast, i} < T_{event, j}
2. The event MUST fall within the horizon validity window (with matching tolerance delta = 5 min):
   T_{event, j} <= T_{forecast, i} + H_i + delta

### 2.2 Earliest First-Warning Rule (No Double Counting)
If multiple forecasts {F_1, F_2, ..., F_k} emit positive alerts preceding attack event E_j, the empirical lead time for E_j is defined exclusively by the **earliest chronological alert**:
T_{first_alert, j} = min_{i in Matches(E_j)} T_{forecast, i}
Delta T_{lead, j} = T_{event, j} - T_{first_alert, j}

Each ground truth attack event can only be matched to **one** earliest warning. Subsequent alerts within the same attack envelope are logged as continuing alerts but do not inflate lead-time statistics or event count.

### 2.3 Unmatched Events and False Alarms
- **Missed Attack (No Preceding Alert)**: E_j has no valid prior alert. The event is recorded as missed, decreasing the empirical_forecast_coverage_rate.
- **False Alarm (Alert with No Event)**: A positive forecast alert F_i that is not followed by an attack event within [T_{forecast, i}, T_{forecast, i} + H_i + delta] is recorded as an unvalidated alert.

---

## 3. Empirical Lead-Time Metrics

Given M matched attack events out of N total attack events:

1. **Mean Lead Time**:
   mu_lead = (1 / M) * sum(Delta T_{lead, j})
2. **Median Lead Time**:
   Median_lead = Median({Delta T_{lead, j}})
3. **Empirical Forecast Coverage Rate**:
   Coverage = (M / N) * 100%
4. **Earliest Warning Horizon Distribution**:
   The count and proportion of attack events where the earliest warning originated from +5m, +15m, +30m, or +60m models.

---

## 4. Insufficient Data Guardrail

When telemetry history contains fewer than 2 valid forecast-event matches, the system does not extrapolate or hallucinate metrics. It explicitly sets:
status = 'INSUFFICIENT_EMPIRICAL_MATCHES' and leaves lead-time statistics null.
