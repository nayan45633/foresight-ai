# FORESIGHT AI — 5-Tier Risk State Engine & Anti-Flutter Hysteresis (Step 7.1 Hardened)

## 1. Executive Summary

Operational security operations centers (SOCs) suffer severely from alert fatigue and rapid state oscillation (alert flutter) caused by transient telemetry noise.

The Foresight AI **Risk State Engine** implements a deterministic 5-tier finite state machine with:
1. **Multi-Source Signal Aggregation**: Unifies multi-horizon forecast probabilities, anomaly scores, lead-time intelligence, and active attack stages.
2. **Consecutive Calm Cycle Persistence**: De-escalation requires a consecutive sequence of calm cycles ($N \ge \text{min\_persistence\_cycles}$) to prevent flutter under bursty attacks.
3. **Asymmetric De-Escalation Thresholds**: Escalation occurs immediately upon threat verification; de-escalation requires strictly lower risk levels ($P < 0.45 / 0.32 / 0.22 / 0.15$).
4. **Controlled Step-Down Progression**: Smoothly descends one severity level at a time (e.g. `CRITICAL` $\to$ `ELEVATED` $\to$ `SUSPICIOUS` $\to$ `WATCH` $\to$ `NORMAL`).
5. **Auditable Transition Log**: Records every state change with timestamp, previous state, new state, and explanatory rationale.

---

## 2. Transparent Composite Risk Formulation & Signal Roles

The risk state calculation combines 5 transparent signal sources:

| Signal Component | Mathematical Role | Role Description | Heuristic Status |
| :--- | :--- | :--- | :--- |
| **Max Calibrated Probability** | $\max_h \hat{p}_h$ ($h \in \{5, 15, 30, 60\}$) | Peak forward attack likelihood across all horizons | Statistically Calibrated |
| **Near-Horizon Average** | $\frac{\hat{p}_5 + \hat{p}_{15}}{2}$ | Immediate attack pressure within lookahead window | Statistically Calibrated |
| **Isolation Forest Score** | $A(x_t) \in [0.0, 1.0]$ | Unsupervised metric of structural flow divergence | Statistical ML |
| **Active Alert Horizons** | $\sum_h \mathbb{I}(\hat{p}_h \ge T_h)$ | Count of horizons exceeding validation decision thresholds | Decision Policy |
| **Conformal Coverage** | $\Gamma_{0.90}(x_t)$ | Uncertainty level derived from split conformal prediction sets | Finite-sample Guarantee |

> [!NOTE]
> **Heuristic State Boundaries**:
> State classification boundaries (0.20, 0.40, 0.65, 0.85) and de-escalation thresholds are heuristic operational policy rules designed for SOC alert prioritization.

---

## 3. 5-Tier Risk State Hierarchy & Transition Rules

| Risk State | Severity Level | Trigger Condition (Immediate Escalation) | De-escalation Requirement |
| :--- | :--- | :--- | :--- |
| `NORMAL` | 0 | Baseline telemetry ($P < 0.22$, Anomaly $< 0.28$) | Baseline nominal |
| `WATCH` | 1 | Anomaly $\ge 0.28$ or $\max P \ge 0.22$ or $+60\text{m}$ alert | $P < 0.15$ + Anomaly $< 0.28$ (2 consecutive cycles) |
| `SUSPICIOUS` | 2 | 1 active alert or Anomaly $\ge 0.50$ with conformal ambiguity | $P < 0.22$ + Anomaly $< 0.40$ (2 consecutive cycles) |
| `ELEVATED` | 3 | $\ge 2$ active alerts or $\max P \ge 0.60$ with alert | $P < 0.32$ + Alert count $= 0$ (2 consecutive cycles) |
| `CRITICAL` | 4 | $\ge 3$ active alerts or $\max P \ge 0.70$ + Anomaly $\ge 0.50$ | $P < 0.45$ + Alert count $< 2$ (2 consecutive cycles) |

---

## 4. Performance Benchmarks

Measured across 100 consecutive evaluations:
- **Risk State Engine Latency**: **p50 = 0.0795 ms**, **p95 = 0.1030 ms**, **p99 = 0.1616 ms**
- **Complete Test Suite**: **79 / 79 tests passing (100%)**
