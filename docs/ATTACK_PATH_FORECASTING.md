# FORESIGHT AI — Evidence-Constrained Attack Path Forecasting Engine (Step 7.1 Hardened)

## 1. Executive Summary

Traditional Intrusion Detection Systems (IDS) and Security Information and Event Management (SIEM) tools analyze security incidents post-hoc or as isolated point-in-time alerts. Foresight AI introduces an **Evidence-Constrained Attack Path Forecasting Engine** that maps telemetry and multi-horizon forecasting models to a **Directed Attack Stage Transition Graph**.

### Core Scientific Principles (Step 7.1 Hardening):
1. **Separation of Graph Knowledge vs. Forecast Probabilities**:
   - The existence of a directed edge in the domain stage graph (e.g. $\text{Scanning} \to \text{Initial Access}$) represents taxonomic domain topology.
   - A *Forecasted Transition Probability* $P(S_{t+h} = s_k \mid \mathcal{X}_t)$ is ONLY provided when statistically supported by calibrated multi-horizon models ($P \ge 0.25$ or active binary alert).
2. **Zero Downstream Probability Invention**:
   - Downstream / subsequent stages are tagged `POTENTIAL_UNVALIDATED` with `probability = null` and `status = GRAPH_POSSIBLE`. Heuristic multiplications (e.g., $P \times 0.7$) are strictly prohibited.
3. **Honest Empty State**:
   - When real telemetry stream is absent, the engine reports `AWAITING_TELEMETRY` rather than fabricating synthetic transitions.
4. **Appropriate Terminology**:
   - Replaced speculative "causal" claims with mathematically grounded "evidence-constrained attack path forecasting" and "directed stage transition graphs".

---

## 2. Directed Attack Stage Transition Graph (Topology)

The engine models adversary movement across 10 sequential operational stages (MITRE ATT&CK / Kill Chain taxonomy):

```
[ RECONNAISSANCE ] ---> [ SCANNING ] ---> [ INITIAL ACCESS ] ---> [ EXECUTION ] ---> [ PERSISTENCE ]
                                                                                             |
[ IMPACT ] <--- [ EXFILTRATION ] <--- [ COMMAND & CONTROL ] <--- [ LATERAL MOVEMENT ] <--- [ PRIVILEGE ESCALATION ]
```

### 2.1 Stage Definitions & Telemetry Behavioral Indicators

| Stage ID | Operational Stage | Primary Telemetry Behavioral Indicators | Forward Horizon Coupling |
| :--- | :--- | :--- | :--- |
| `RECONNAISSANCE` | Passive/Active Probing | Low-rate multi-port access, elevated source entropy, ICMP/DNS anomalous rates | $+60\text{m}, +30\text{m}$ |
| `SCANNING` | Port & Service Discovery | High SYN-to-ACK ratio ($> 0.50$), high packet rate ($> 400\text{ PPS}$), low duration | $+30\text{m}, +15\text{m}$ |
| `INITIAL_ACCESS` | Vulnerability Exploit | High anomaly score ($> 0.50$), payload asymmetry, forward risk ($P > 0.40$) | $+15\text{m}, +5\text{m}$ |
| `EXECUTION` | Payload Delivery | Unbalanced payload length variance, high sustained byte rates (BPS) | $+15\text{m}, +5\text{m}$ |
| `PERSISTENCE` | Beaconing & Heartbeats | Periodic low-jitter flow intervals, persistent connection durations | $+30\text{m}, +15\text{m}$ |
| `PRIVILEGE_ESCALATION` | Local Escalation Probes | Burst connection spikes to internal management services | $+15\text{m}, +5\text{m}$ |
| `LATERAL_MOVEMENT` | Internal Propagation | High internal fan-out, horizontal SMB/RPC/SSH traversal patterns | $+15\text{m}, +5\text{m}$ |
| `COMMAND_AND_CONTROL` | External C2 Channels | High flow duration entropy, asymmetric out-to-in volume, periodic beacons | $+30\text{m}, +15\text{m}$ |
| `EXFILTRATION` | Outbound Data Transfer | Extreme outbound-to-inbound byte ratio, prolonged outbound flows ($> 500\text{ KB}$) | $+15\text{m}, +5\text{m}$ |
| `IMPACT` | Denial of Service / Disruption | Extreme PPS ($> 1000$), massive SYN flood, high RST ratio ($> 0.45$) | $+5\text{m}$ |

---

## 3. Transition Likelihood & Confidence Levels

Transition confidence is categorized into 4 rigorous operational tiers:
- **`VALIDATED_TRANSITION`**: Next-stage transition supported by calibrated probability $\ge 0.25$ or active decision threshold alert.
- **`INSUFFICIENT_EVIDENCE`**: Telemetry and forward models indicate normal baseline activity ($P < 0.25$).
- **`BENIGN_NOMINAL`**: Zero anomalous telemetry deviations detected; system operating at baseline nominal distribution.
- **`AWAITING_TELEMETRY`**: Telemetry buffer has not yet accumulated sufficient flow volume for sliding window extraction.

---

## 4. Sub-Millisecond Performance Benchmarks

Step 7.1 latency benchmarks measured across 100 consecutive production evaluations:

| Component | p50 (Median) | p95 | p99 | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Attack Path Evaluation** | **0.0281 ms** | **0.0614 ms** | **0.0811 ms** | $< 1.0\text{ ms}$ | **PASSED (35x faster)** |
| **Risk State Engine** | **0.0795 ms** | **0.1030 ms** | **0.1616 ms** | $< 1.0\text{ ms}$ | **PASSED (12x faster)** |

---

## 5. API Endpoints

- `GET /api/v1/risk/state`: Current evaluated risk state grounded in real network flows.
- `GET /api/v1/risk/attack-path`: Directed transition graph strictly separating forecasted edges from unvalidated graph topology.
- `GET /api/v1/risk/timeline`: Chronological timeline of risk evaluations.
- `GET /api/v1/risk/transitions`: Chronological audit log of state escalations and de-escalations.
- `GET /api/v1/risk/demo-state`: Explicit demo endpoint executing benchmark telemetry.
