# FORESIGHT AI — Machine Learning Experimentation & Benchmark Log (Step 4)

## 1. Executive Summary

This document records the empirical results, calibration experiments, conformal prediction evaluation, and held-out test benchmarks for **Foresight AI**'s Step 4 Uncertainty & Calibration System (`v1.0.0-temporal-gbm`).

All calibration methods and conformal quantile thresholds were evaluated and frozen **strictly on the Validation partition**. The held-out test partition ($N = 432$ windows, 20.4h – 24.0h) was evaluated **exactly once** after all artifacts were frozen.

---

## 2. Candidate Calibration Experimentation (Validation Partition Only)

Evaluated candidate methods:
1. `NONE`: Raw HistGBM tree probabilities
2. `PLATT_SIGMOID`: Logistic regression scaling
3. `ISOTONIC`: Non-parametric piecewise isotonic regression
4. `BETA`: Bivariate logistic calibration on log-odds features

### Validation Partition Calibration Comparison ($N = 433$ windows)

| Horizon | Candidate Method | Brier Score | ECE | MCE | Log Loss | Selected on Validation? |
|---|---|---|---|---|---|---|
| **+5m** | NONE | 0.0226 | 0.0267 | 0.9873 | 0.0968 | No |
| | PLATT_SIGMOID | 0.0218 | 0.0017 | 0.1182 | 0.0996 | No |
| | **ISOTONIC** | **0.0150** | **0.0000** | **0.0000** | **0.0439** | **YES (Optimal)** |
| | BETA | 0.0181 | 0.0143 | 0.3512 | 0.0621 | No |
| **+15m** | NONE | 0.0047 | 0.0066 | 0.6560 | 0.0229 | No |
| | PLATT_SIGMOID | 0.0068 | 0.0273 | 0.3303 | 0.0440 | No |
| | **ISOTONIC** | **0.0022** | **0.0000** | **0.0000** | **0.0092** | **YES (Optimal)** |
| | BETA | 0.0044 | 0.0027 | 0.4508 | 0.0210 | No |
| **+30m** | NONE | 0.0743 | 0.0484 | 0.8351 | 0.2897 | No |
| | PLATT_SIGMOID | 0.0732 | 0.0284 | 0.6762 | 0.2750 | No |
| | **ISOTONIC** | **0.0666** | **0.0000** | **0.0000** | **0.2364** | **YES (Optimal)** |
| | BETA | 0.0695 | 0.0092 | 0.6108 | 0.2548 | No |
| **+60m** | NONE | 0.1738 | 0.0951 | 0.7637 | 0.5266 | No |
| | PLATT_SIGMOID | 0.1677 | 0.0456 | 0.5224 | 0.5123 | No |
| | **ISOTONIC** | **0.1527** | **0.0000** | **0.0000** | **0.4704** | **YES (Optimal)** |
| | BETA | 0.1601 | 0.0184 | 0.5841 | 0.4912 | No |

---

## 3. Final Step 4 Evaluation on Held-Out Test Set (Evaluated ONCE)

Evaluated on untouched held-out test partition ($N = 432$ windows) with frozen validation thresholds and conformal quantiles ($1 - \alpha = 0.90$):

| Horizon | Selected Method | Threshold | Brier | ECE | MCE | Log Loss | F1-Score | Conformal Coverage | Avg Set Size | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **+5m** | ISOTONIC | 0.2632 | **0.0193** | **0.0137 (1.37%)** | 0.1287 | 0.0732 | 0.4500 | **92.1%** | 0.92 | **CALIBRATED** |
| **+15m** | ISOTONIC | 1.0000 | **0.0092** | **0.0060 (0.60%)** | 0.0784 | 0.0381 | **0.9310** | **92.6%** | 0.93 | **CALIBRATED** |
| **+30m** | ISOTONIC | 1.0000 | **0.0756** | **0.0334 (3.34%)** | 0.2114 | 0.2549 | 0.5977 | **92.1%** | 1.00 | **CALIBRATED** |
| **+60m** | ISOTONIC | 0.2656 | **0.1653** | **0.0464 (4.64%)** | 0.3842 | 0.4812 | 0.4278 | **91.4%** | 1.56 | **WATCH** |

---

## 4. Conformal Prediction Coverage Breakdown

- **Target Coverage**: $90.0\%$ ($1 - \alpha = 0.90$)
- **Observed Test Set Coverage**:
  - **+5m**: $92.1\%$ empirical coverage (Average set size: $0.92$, $92.1\%$ singletons, $0.0\%$ ambiguous)
  - **+15m**: $92.6\%$ empirical coverage (Average set size: $0.93$, $92.6\%$ singletons, $0.0\%$ ambiguous)
  - **+30m**: $92.1\%$ empirical coverage (Average set size: $1.00$, $92.1\%$ singletons, $0.0\%$ ambiguous)
  - **+60m**: $91.4\%$ empirical coverage (Average set size: $1.56$, $44.0\%$ singletons, $56.0\%$ ambiguous sets $\{0, 1\}$)

> **Insight**: The +60m horizon naturally emits wider conformal sets $\{0, 1\}$ on $56\%$ of test samples, accurately communicating to SOC decision policies that 1-hour lookahead exhibits higher forecast ambiguity and entropy while maintaining the marginal $\ge 90\%$ coverage guarantee under exchangeability.

---

## 5. Inference Latency & Performance Breakdown

Empirically measured latencies:
- **Raw Ensemble Inference (Single Horizon)**: $3.003\text{ ms}$
- **Isotonic Calibration Transformation**: $0.159\text{ ms}$
- **Split Conformal Prediction Set Lookup**: $0.012\text{ ms}$
- **Behavioral Anomaly Detector**: $12.339\text{ ms}$
- **Complete 4-Horizon End-to-End Pipeline**: **$25.044\text{ ms}$**
