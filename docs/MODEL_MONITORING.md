# Foresight AI — Statistical Model Monitoring Methodology

This document outlines the statistical theory, metrics, thresholds, and operational rules governing the Foresight AI model monitoring subsystem.

---

## 1. Monitoring Domains & Hierarchy

The Foresight AI Model Monitoring architecture observes six distinct analytical domains:

```
                          ┌──────────────────────────┐
                          │   Composite Model Health │
                          └─────────────┬────────────┘
                                        │
     ┌──────────────────┬───────────────┴──────────────┬──────────────────┐
     ▼                  ▼                              ▼                  ▼
┌──────────────┐ ┌──────────────┐             ┌─────────────────┐ ┌──────────────┐
│ Data Quality │ │Feature Drift │             │Prediction Drift │ │ Calibration  │
│  Validation  │ │  (PSI / KS)  │             │ & Distribution  │ │ & Conformal  │
└──────────────┘ └──────────────┘             └─────────────────┘ └──────────────┘
                                                       │
                                              ┌────────┴────────┐
                                              ▼                 ▼
                                     ┌─────────────────┐ ┌──────────────┐
                                     │Multi-Horizon Acc│ │Empirical Lead│
                                     │(+5m/15m/30m/60m)│ │ Time Tracking│
                                     └─────────────────┘ └──────────────┘
```

---

## 2. Statistical Methodology

### 2.1 Feature Drift (PSI & Kolmogorov-Smirnov)
For continuous numerical features in the authoritative 37-feature schema:

1. **Population Stability Index (PSI)**:
   $$\text{PSI} = \sum_{b=1}^{B} \left( P_{\text{actual}}(b) - P_{\text{expected}}(b) \right) \times \ln\left( \frac{P_{\text{actual}}(b)}{P_{\text{expected}}(b)} \right)$$
   where $B = 10$ quantile bins established on the baseline reference dataset.

   **Standard Interpretation Thresholds**:
   - $\text{PSI} < 0.10$: Negligible shift (`HEALTHY` / `NO_DRIFT`)
   - $0.10 \le \text{PSI} < 0.25$: Moderate shift (`WATCH` / `MODERATE_DRIFT`)
   - $\text{PSI} \ge 0.25$: Significant shift (`DRIFT_DETECTED` / `DEGRADED`)

2. **Kolmogorov-Smirnov (KS) Two-Sample Test**:
   $$D_{\text{KS}} = \sup_{x} |F_1(x) - F_2(x)|$$
   - Minimum sample size guard: $N \ge 30$ samples required in the current observation window. If $N < 30$, the system explicitly returns `INSUFFICIENT_DATA`.

### 2.2 Prediction Distribution Shift
Monitors the empirical density of calibrated output probabilities $\hat{p}_t^{(H)}$ across sliding observation windows ($N = 100$ predictions):
- Positive forecast decision rate ($\hat{p}_t \ge \tau_H$)
- Distribution percentiles ($p_{10}, p_{50}, p_{90}$)
- Shift classification: `STABLE`, `ELEVATED_THREAT_ACTIVITY`, or `PREDICTION_DISTRIBUTION_SHIFT`.

### 2.3 Calibration Monitoring (Brier Score & ECE)
Evaluated strictly when ground truth event labels $y_t \in \{0, 1\}$ are recorded:
- **Brier Score**:
  $$\text{BS} = \frac{1}{N} \sum_{i=1}^N (\hat{p}_i - y_i)^2$$
- **Expected Calibration Error (ECE)**:
  $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} |\text{acc}(B_m) - \text{conf}(B_m)|$$
- **Conformal Marginal Coverage**:
  $$\hat{\alpha}_{\text{emp}} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(y_i \in \hat{C}(x_i))$$
- **Absence of Ground Truth**: If no verified event labels are present in the observation window, the API returns `AWAITING GROUND TRUTH` rather than computing synthetic or misleading calibration metrics.

### 2.4 Multi-Horizon Performance
Metrics (Precision, Recall, F1, PR-AUC, Empirical Lead-Time) are tracked independently for each distinct forecast horizon:
- $+5\text{m}$ (Imminent attack detection)
- $+15\text{m}$ (Tactical early warning)
- $+30\text{m}$ (Operational early warning)
- $+60\text{m}$ (Strategic posture adjustment)

Horizons are never blended or averaged together. If sample sizes of confirmed attack incidents are $< 5$, the system renders `INSUFFICIENT EMPIRICAL EVIDENCE`.

---

## 3. Data Quality & Composite Model Health State

### 3.1 Data Quality States
- `HEALTHY`: 0% missing, 0% NaN/Inf, all features within baseline empirical min-max ranges.
- `WATCH`: $< 1\%$ minor range excursions or $< 0.1\%$ duplicate telemetry flows.
- `DEGRADED`: Missing values present, rate anomalies $> 5\%$, or protocol distribution divergence.
- `CRITICAL`: Schema mismatch, corrupted flow records, or $> 10\%$ invalid data points.

### 3.2 Composite Model Health State Machine
The composite state is determined deterministically from underlying sub-signals:
- `CRITICAL`: If artifact integrity verification fails (SHA-256 mismatch), schema is invalid, or data quality is `CRITICAL`.
- `DEGRADED`: If feature drift is detected across $\ge 5$ core features ($\text{PSI} \ge 0.25$) OR calibration error exceeds $\text{ECE} > 0.15$.
- `WATCH`: If moderate drift is observed ($0.10 \le \text{PSI} < 0.25$) OR minor data quality warnings exist.
- `HEALTHY`: All underlying indicators are within normal tolerances.
