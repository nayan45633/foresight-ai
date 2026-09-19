# FORESIGHT AI — Forecasting Methodology, Calibration & Conformal Uncertainty

## 1. Detection vs. Forecasting Distinction

Traditional Network Intrusion Detection Systems (NIDS) solve an instantaneous detection problem:
$$\hat{y}(t) = f\left(X(t)\right)$$
where $X(t)$ is the current traffic slice and $y(t)$ is the current attack state. This triggers alerts only *after* malicious packets have already breached the perimeter.

**Foresight AI** formulates a proactive forward temporal forecasting problem:
$$\hat{y}(t + h) = f\left(\{X(t - k \cdot S)\}_{k=0}^{K-1}, h\right)$$
where $h \in \{5\text{m}, 15\text{m}, 30\text{m}, 60\text{m}\}$ represents the lookahead horizon, $W=60\text{s}$ is the sliding window width, and $S=30\text{s}$ is the stride.

```
       HISTORICAL TELEMETRY WINDOWS                  PREDICTIVE HORIZONS
[ t - 90s ]  [ t - 60s ]  [ t - 30s ]  [ t (Now) ] ---> [ t + 5m ]  [ t + 15m ]  [ t + 30m ]  [ t + 60m ]
                                                            |           |            |            |
                                                            v           v            v            v
                                                         Early       Pre-Attack    Policy      Capacity
                                                         Tuning      Isolation     Update      Planning
```

---

## 2. Core Statistical Terminology & Semantics

In Foresight AI, the following statistical concepts are strictly distinguished:

1. **Calibrated Probability ($\hat{p}$)**:
   The estimated conditional likelihood $P(Y(t+h) = 1 \mid X=x)$ that an attack event will materialize within the forward horizon interval $[t, t+h]$, calibrated against empirical validation frequencies.
2. **Operational Decision Threshold ($T_h$)**:
   A decision boundary selected on validation data (e.g., maximizing validation $F_1$-score) used to produce binary alert decisions:
   $$\text{Alert} = \mathbb{I}(\hat{p} \ge T_h)$$
   A positive alert decision is an operational classification rule and does NOT imply statistical certainty.
3. **Probability Calibration**:
   The alignment between predicted probabilities and empirical frequencies:
   $$P\left(Y(t+h) = 1 \mid \hat{p} = p\right) \approx p \quad \forall p \in [0, 1]$$
4. **Split Conformal Prediction Set ($\Gamma_{1-\alpha}(x)$)**:
   A distribution-free prediction set satisfying finite-sample marginal coverage under the assumption of exchangeability between calibration and test distributions:
   $$P\left(Y_{n+1} \in \Gamma_{1-\alpha}(X_{n+1})\right) \ge 1 - \alpha$$
5. **Uncertainty Indicators**:
   Normalized metrics reflecting forecast dispersion, behavioral anomaly distance, and prediction set ambiguity. The system does not separately identify or quantify epistemic vs. aleatoric uncertainty.

---

## 3. Probability Calibration Architecture

Tree-based boosting forecasters output uncalibrated leaf score proportions. Foresight AI evaluates four calibration regimes on the **Validation partition only**:

1. **No-Op Calibration**: $\hat{p}_{\text{cal}} = \hat{p}_{\text{raw}}$
2. **Platt Sigmoid Scaling**:
   $$\hat{p}_{\text{cal}} = \frac{1}{1 + \exp\left(-(A \cdot \hat{p}_{\text{raw}} + B)\right)}$$
3. **Isotonic Regression**: Piecewise constant non-decreasing monotonic fit.
4. **Beta Calibration** (Kull et al., 2017):
   $$\hat{p}_{\text{cal}} = \frac{1}{1 + 1 / \left(C \cdot \hat{p}^a / (1-\hat{p})^b\right)}$$

### Evaluated Calibration Metrics
- **Expected Calibration Error (ECE)**:
   $$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
- **Maximum Calibration Error (MCE)**:
   $$\text{MCE} = \max_{m=1,\dots,M} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
- **Brier Score Loss**:
   $$\text{Brier} = \frac{1}{N} \sum_{i=1}^{N} (\hat{p}_i - y_i)^2$$

---

## 4. Binary Split Conformal Prediction

To deliver distribution-free marginal coverage guarantees without parametric distribution assumptions, Foresight AI implements **Split Conformal Prediction**:

1. **Non-Conformity Score**:
   $$s_i = 1 - \hat{p}(y_i \mid x_i) = \begin{cases} 1 - \hat{p}_i & \text{if } y_i = 1 \\ \hat{p}_i & \text{if } y_i = 0 \end{cases}$$
2. **Conformal Quantile Threshold**:
   For target coverage $1 - \alpha = 0.90$, with $n$ validation calibration samples:
   $$\hat{q} = \text{Quantile}\left(\{s_i\}_{i=1}^n, \frac{\lceil (n+1)(1-\alpha) \rceil}{n}\right)$$
3. **Prediction Set Formation**:
   $$\Gamma_{1-\alpha}(x) = \{y \in \{0, 1\} : (1 - \hat{p}(y \mid x)) \le \hat{q}\}$$
   - **$\{0\}$**: Label 0 (benign) was not excluded by the conformal procedure at the $1-\alpha$ level.
   - **$\{1\}$**: Label 1 (attack) was not excluded by the conformal procedure at the $1-\alpha$ level.
   - **$\{0, 1\}$**: Neither label was excluded (forecast ambiguity / high uncertainty).
   - **$\emptyset$**: High uncertainty / conformal rejection (neither class satisfied the inclusion rule).

> [!NOTE]
> Split Conformal Prediction provides marginal coverage across datasets under exchangeability; it does not provide an individual posterior probability guarantee for any single prediction. Prediction sets serve as inputs to downstream SOC decision policies.

---

## 5. Model Calibration Health Status Taxonomy

Foresight AI deterministically assesses calibration health based on validation metrics:

| Status | Condition | Operational Semantics |
|---|---|---|
| **CALIBRATED** | $\text{ECE} \le 0.05$ and $\text{Brier} \le 0.10$ | Calibration criteria satisfied on validation evaluation |
| **WATCH** | $0.05 < \text{ECE} \le 0.08$ | Minor probability dispersion; valid ranking |
| **LIMITED** | $\text{ECE} > 0.08$ or Sample Count $< 100$ | Elevated calibration error; manual review recommended |
| **UNAVAILABLE** | Missing model/calibration artifacts | Fail-safe standby; no predictions generated |

---

## 6. Scientific Scope & Disclaimer

> [!IMPORTANT]
> Foresight AI forecasts future network attack risk based on historical and temporal telemetry features; it provides calibrated early-warning likelihoods and conformal prediction sets, but does not provide absolute deterministic certainty of future threat manifestation. All automated responses remain subject to downstream SOC operational policies.
