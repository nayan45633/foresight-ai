# FORESIGHT AI — Model Card: `v1.0.0-temporal-gbm` (Step 5 TreeSHAP Attributed)

## Model Details
- **Model Name**: Foresight Multi-Horizon Temporal Gradient Boosting Forecaster
- **Version**: `v1.0.0-temporal-gbm`
- **Architecture**: Ensemble `HistGradientBoostingClassifier` with `RobustScaler` preprocessing + Horizon-Specific `IsotonicCalibrator` + `BinarySplitConformalPredictor` ($1 - \alpha = 0.90$) + `TreeExplainer` (Exact Additive TreeSHAP).
- **Input Dimension**: 37 features (28 window-level base statistical features + 8 rolling temporal derivatives + 1 unsupervised Isolation Forest anomaly score).
- **Output**: Multi-horizon calibrated attack probabilities $P(\text{Attack} \mid \text{Window}_{t}, h) \in [0.0, 1.0]$, distribution-free finite-sample Conformal Prediction Sets $\Gamma_{0.90} \subseteq \{0, 1\}$, and exact TreeSHAP feature attributions $\phi_j \in \mathbb{R}^{37}$ for $h \in \{5\text{m}, 15\text{m}, 30\text{m}, 60\text{m}\}$.
- **Explainability Status**: Exact TreeSHAP additivity verified ($\text{base\_value} + \sum \phi_j = \text{raw\_margin}$ with $\Delta < 10^{-4}$).

---

## Statistical Interpretation & Limitations

### 1. Probability Calibration vs. Decision Thresholds
- **Calibrated Probability**: Represents an empirical estimate of the conditional event frequency $P(Y=1 \mid X=x)$.
- **Operational Decision Threshold**: A separate policy parameter $T_h$ chosen on validation data to optimize classification objectives (e.g., $F_1$-score).
- **Separation of Concerns**: A calibrated probability exceeding a decision threshold ($\hat{p} \ge T_h$) triggers an operational alert decision; it does NOT imply statistical certainty.

### 2. Split Conformal Prediction & Marginal Coverage
- **Marginal Guarantee**: Split Conformal Prediction guarantees $P(Y_{n+1} \in \Gamma_{1-\alpha}(X_{n+1})) \ge 1 - \alpha$ over the joint distribution of $(X, Y)$ under the assumption that calibration and test data are exchangeable.
- **Not a Posterior Guarantee**: A prediction set does not guarantee a $90\%$ correctness probability for any single individual test instance.
- **Non-Exclusion Semantics**:
  - $\{0\}$: Label 0 (benign) was not excluded by the conformal procedure at the $1 - \alpha$ level.
  - $\{1\}$: Label 1 (attack) was not excluded by the conformal procedure at the $1 - \alpha$ level.
  - $\{0, 1\}$: Neither label was excluded (indicates forecast ambiguity / high uncertainty).
  - $\emptyset$ (Empty Set): Neither label satisfied the conformal non-conformity criterion ($s(x, 0) > \hat{q}$ and $s(x, 1) > \hat{q}$), denoting high uncertainty / conformal rejection.
- **Downstream SOC Policy**: Conformal prediction sets serve as structured uncertainty inputs to downstream SOC decision policies; they do not unilaterally determine or mandate automated containment actions.

### 3. SHAP Feature Attribution Scope & Boundaries
- **Margin-Space Decomposition**: TreeSHAP values $\phi_j$ attribute the contribution of individual features to the uncalibrated model decision margin $f(x) = \text{base\_value} + \sum \phi_j$.
- **Attribution is NOT Causality**: Feature importance reflects statistical pattern association within the trained model; it does NOT prove attacker intent or physical causality.

---

## Audited Empirical Performance Summary

### Calibration Method Selection (Validation Data Only)
| Horizon | NoOp Brier | Platt Brier | Beta Brier | Isotonic Brier | Selected Method |
|---|---|---|---|---|---|
| **+5m** | 0.0210 | 0.0205 | 0.0203 | **0.0181** | **Isotonic Regression** |
| **+15m** | 0.0156 | 0.0104 | 0.0102 | **0.0087** | **Isotonic Regression** |
| **+30m** | 0.0862 | 0.0768 | 0.0765 | **0.0712** | **Isotonic Regression** |
| **+60m** | 0.1834 | 0.1712 | 0.1708 | **0.1589** | **Isotonic Regression** |

### Held-Out Test Set (Evaluated Once with Frozen Validation Thresholds)
| Horizon | Calibrator | Threshold | Precision | Recall | F1-Score | Brier Score | ECE | MCE | Conformal Cov. ($1-\alpha=0.90$) | Avg Set Size | Health Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **+5m** | Isotonic | 0.2632 | 0.4500 | 0.4500 | 0.4500 | **0.0193** | **0.0137** (1.37%) | 0.0821 | **92.1%** | 0.92 | `CALIBRATED` |
| **+15m** | Isotonic | 1.0000 | 0.9643 | 0.9000 | 0.9310 | **0.0092** | **0.0060** (0.60%) | 0.0345 | **92.6%** | 0.93 | `CALIBRATED` |
| **+30m** | Isotonic | 1.0000 | 0.9643 | 0.4355 | 0.5977 | **0.0756** | **0.0334** (3.34%) | 0.1204 | **92.1%** | 1.00 | `CALIBRATED` |
| **+60m** | Isotonic | 0.2656 | 0.3125 | 0.6750 | 0.4278 | **0.1653** | **0.0464** (4.64%) | 0.1420 | **91.4%** | 1.56 | `WATCH` |

### Real-Time Latency Benchmark (Measured Empirically)
- **Temporal Derivative Extraction**: **0.055 ms**
- **Isolation Forest Anomaly Scoring**: **12.339 ms**
- **Single-Horizon Model Inference**: **3.003 ms**
- **Isotonic Calibration Lookup**: **0.159 ms**
- **Conformal Prediction Set Generation**: **0.012 ms**
- **TreeSHAP Attribution (4 horizons)**: **0.640 ms**
- **Multi-Horizon Timeline Generation (4 horizons + SHAP + Deltas)**: **66.731 ms (p50)** / **99.512 ms (p95)**
- **Empirical Lead-Time Event Matching Engine (200 forecasts vs GT)**: **0.595 ms (p50)** / **0.908 ms (p95)**
- **Complete End-to-End Timeline Pipeline**: **71.916 ms (mean)**

---

## Multi-Horizon & Empirical Lead-Time Methodology (Step 6)
- **Monotonic Progression Guarantee**: Forecast timestamps strictly enforce $T_0 < T_{+5\text{m}} < T_{+15\text{m}} < T_{+30\text{m}} < T_{+60\text{m}}$.
- **Empirical First-Warning Policy**: Attacks are matched strictly to the earliest valid positive alert in $[T_{\text{event}}-H-\delta, T_{\text{event}})$.
- **Double Counting Elimination**: Each ground-truth attack event is credited with at most one earliest warning; duplicate alerts do not inflate lead-time statistics.
- **Fail-Safe Insufficient Data State**: If matched events $< 2$, metrics are returned as null with `INSUFFICIENT_EMPIRICAL_MATCHES` status without speculative imputation.

- **Attack Path Evaluation Latency (Step 7)**: **0.038 ms (p50)** / **0.064 ms (p95)**
- **Risk State Machine Evaluation Latency (Step 7)**: **0.055 ms (p50)** / **0.076 ms (p95)**

---

## Attack Path Forecasting & Risk State Engine (Step 7)
- **10-Stage MITRE / Kill-Chain Directed Causal Graph**: Reconnaissance -> Scanning -> Initial Access -> Execution -> Persistence -> Privilege Escalation -> Lateral Movement -> Command & Control -> Exfiltration -> Impact.
- **5-Tier Risk State Machine**: `NORMAL`, `WATCH`, `SUSPICIOUS`, `ELEVATED`, `CRITICAL` with deterministic multi-signal aggregation.
- **Hysteresis Anti-Flutter**: Asymmetric de-escalation thresholds ($R_{\text{comp}} < 0.75 / 0.55 / 0.30 / 0.12$) with cooldown cycle requirements (1–3 cycles).
- **Zero-Fabrication Data Honesty**: Returns `BENIGN_NOMINAL` / `INSUFFICIENT_EVIDENCE` when telemetry displays baseline behavior.
