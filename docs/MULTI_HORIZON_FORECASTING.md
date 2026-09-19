# Multi-Horizon Temporal Forecasting Intelligence Engine

## 1. Executive Summary & Temporal Philosophy

Foresight AI departs from reactive intrusion detection systems by estimating breach risk across a structured discrete sequence of forward temporal horizons:
- **5 Minutes** (H_5): Immediate operational threat window (tactical mitigation, real-time filtering).
- **15 Minutes** (H_15): Short-term staging / reconnaissance evolution window.
- **30 Minutes** (H_30): Intermediate lateral movement and payload deployment window.
- **60 Minutes** (H_60): Strategic early-warning horizon (campaign detection, automated quarantine preparation).

A valid multi-horizon forecast is not a collection of independent uncoordinated point estimates. It represents a coherent temporal trajectory across future time intervals.

---

## 2. Mathematical Formalization & Temporal Monotonicity

Let T_forecast denote the timestamp at which telemetry inference is executed (the current observation baseline T_0).

### 2.1 Forward Horizon Timestamps
For each discrete horizon h in {5, 15, 30, 60} minutes:
T_target(h) = T_forecast + h * 60 seconds

### 2.2 Strict Temporal Monotonicity Requirement
A forecast timeline is rejected as invalid if strict forward chronological progression is violated:
T_forecast < T_target(5m) < T_target(15m) < T_target(30m) < T_target(60m)
Any backward-looking timestamp, out-of-order horizon, or non-monotonic progression raises a ValueError in the validation layer.

### 2.3 Horizon-to-Horizon Probability Trajectory (Delta P)
Risk evolution across adjacent temporal intervals is computed via forward probability deltas:
Delta P(h_i -> h_{i+1}) = P(Y_{t+h_{i+1}} = 1 | X_t) - P(Y_{t+h_i} = 1 | X_t)

- **Delta P > 0 (Escalating Risk)**: Attack likelihood increases further into the future, indicating slow-burn staging or pre-attack reconnaissance.
- **Delta P approx 0 (Sustained Risk)**: Threat probability is persistent across operational horizons.
- **Delta P < 0 (De-escalating Risk)**: Elevated immediate risk that subsides over longer horizons.

---

## 3. Dynamic Earliest Warning Identification

Rather than assuming a fixed horizon is always superior, the system dynamically identifies the **Earliest Warning Horizon**:
1. Filter horizons where the calibrated forecast probability strictly meets or exceeds the frozen horizon decision threshold:
   H_alert = { h in {5, 15, 30, 60} | P_calibrated(h) >= tau_h }
2. If H_alert is non-empty, the earliest warning horizon is the maximum lookahead horizon in H_alert:
   h* = max(H_alert)
3. If no horizon triggers an alert (H_alert is empty), h* = None (nominal state).
---
## 4. Distinction Between Concepts

Calibrated Probability != Confidence != Decision Threshold != Uncertainty != Theoretical Horizon != Empirical Lead Time.