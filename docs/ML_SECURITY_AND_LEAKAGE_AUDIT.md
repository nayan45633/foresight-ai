# Foresight AI — Machine Learning Security & Data Leakage Audit

This document details the mathematical and operational data leakage audit across the Foresight AI machine learning pipeline, encompassing feature extraction, temporal window slicing, multi-horizon label alignment, calibration, conformal prediction, and explainability.

---

## 1. Temporal Integrity & Chronological Splitting

### 1.1 Strict Temporal Order Enforcement
In cyber-attack forecasting, standard random cross-validation ($k$-fold) causes severe data leakage because network flows exhibiting coordinated attack scans or lateral movement share underlying statistical correlations across time.

**Audit Verification**:
- **Dataset Splitting**: The dataset is strictly partitioned chronologically:
  $$\mathcal{D}_{\text{train}} = \{x_t, y_t\}_{t=0}^{T_{\text{train}}}, \quad \mathcal{D}_{\text{val}} = \{x_t, y_t\}_{t=T_{\text{train}}+1}^{T_{\text{val}}}, \quad \mathcal{D}_{\text{test}} = \{x_t, y_t\}_{t=T_{\text{val}}+1}^{T_{\text{test}}}$$
  where $T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$.
- **No Test Information in Scaling / Normalization**: Scalers (e.g. RobustScaler / StandardScaler) and imputation statistics are fitted strictly on $\mathcal{D}_{\text{train}}$ and subsequently transformed on $\mathcal{D}_{\text{val}}$ and $\mathcal{D}_{\text{test}}$.

---

## 2. Rolling Window & Feature Construction Audit

### 2.1 Backward-Only Lookback
Features are calculated using sliding observation windows over historical time only:
$$W_t = [t - \Delta t_{\text{obs}}, t]$$
where $\Delta t_{\text{obs}} = 60\text{ seconds}$.

- **Derivative and Momentum Features**: Packet rate derivatives ($\Delta \text{pkt}/\Delta t$) and entropy fluctuations are computed strictly within $[t - \Delta t_{\text{obs}}, t]$. No forward-looking rolling averages or centered windows are utilized.
- **Label Generation**: For each prediction horizon $H \in \{+5\text{m}, +15\text{m}, +30\text{m}, +60\text{m}\}$, the target label is defined as:
  $$Y_{t}^{(H)} = \mathbb{I}\left(\text{Attack Event in } [t, t + H]\right)$$
  The label window begins *at or after* $t$, ensuring that feature computation $W_t$ and target assessment are temporally disjoint except at the current timestamp $t$.

---

## 3. Calibration & Conformal Prediction Integrity

### 3.1 Independent Calibration Split
- **Isotonic & Sigmoid Calibrators**: Calibrators are fitted exclusively on the validation partition $\mathcal{D}_{\text{val}}$ after the base boosting models have converged on $\mathcal{D}_{\text{train}}$. No test samples $\mathcal{D}_{\text{test}}$ are used in calibration fitting.
- **Conformal Prediction Sets**: Split conformal quantile thresholds $\hat{q}_{\alpha}$ are computed on the held-out calibration partition:
  $$\hat{q}_{\alpha} = \text{Quantile}_{1 - \alpha}\left(\{s_i\}_{i \in \mathcal{D}_{\text{cal}}}\right)$$
  ensuring valid marginal coverage:
  $$\mathbb{P}\left(Y_{n+1} \in \hat{C}(X_{n+1})\right) \ge 1 - \alpha$$
  under the assumption of exchangeability between calibration and test distributions.

---

## 4. SHAP Explainability & Leakage Prevention

- **Background Dataset**: TreeSHAP background dataset uses $K = 100$ representative medoid samples extracted strictly from $\mathcal{D}_{\text{train}}$.
- **Additivity Verification**: For every forecast $f(x)$, local feature attributions $\phi_i$ are mathematically validated to satisfy local accuracy (additivity):
  $$f(x) = \phi_0 + \sum_{i=1}^{37} \phi_i(x) \pm \epsilon, \quad |\epsilon| < 10^{-4}$$

---

## 5. Audit Conclusions

| Pipeline Stage | Leakage Risk Level | Implemented Mitigation | Verification Status |
| :--- | :---: | :--- | :---: |
| **Feature Extraction** | None | Strictly backward-looking windows ($[t-60s, t]$) | ✅ Verified |
| **Data Partitioning** | None | Chronological temporal split ($t_{\text{train}} < t_{\text{val}} < t_{\text{test}}$) | ✅ Verified |
| **Model Scaling** | None | Fitted solely on train partition; applied to val/test | ✅ Verified |
| **Probability Calibration** | None | Independent calibration split $\mathcal{D}_{\text{cal}}$ | ✅ Verified |
| **Conformal Prediction** | None | Split conformal quantiles derived on $\mathcal{D}_{\text{cal}}$ | ✅ Verified |
| **TreeSHAP Attributions** | None | Background medoids sourced strictly from train set | ✅ Verified |
| **Empirical Lead Time** | None | Evaluated post-hoc on verified incident ground-truth | ✅ Verified |
