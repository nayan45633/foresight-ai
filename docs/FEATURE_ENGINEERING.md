# Foresight AI — Mathematical Feature Engineering Specification

The **Statistical Feature Extraction Engine** (`app/telemetry/feature_extractor.py`) computes 28 dense mathematical behavior features per temporal window for the downstream ML Forecasting Engine.

---

## Feature Taxonomy & Mathematical Formulations

### 1. Volumetric & Rate Features
- **`flow_volume`**: Total count of active flows in window $W$:
  $$N_f = |\{f \in W\}|$$
- **`packet_volume`**: Total packets transmitted:
  $$N_p = \sum_{f \in W} f.\text{packet\_count}$$
- **`byte_volume`**: Total bytes transmitted:
  $$N_b = \sum_{f \in W} f.\text{byte\_count}$$
- **`packets_per_second`**: Effective packet throughput rate:
  $$\lambda_p = \frac{N_p}{\Delta t}$$
- **`bytes_per_second`**: Effective byte throughput rate:
  $$\lambda_b = \frac{N_b}{\Delta t}$$

---

### 2. Directional & Volumetric Ratios
- **`forward_backward_ratio`**: Ratio of initiator packets to responder packets:
  $$R_{fb} = \frac{\sum f.\text{forward\_packets}}{\max(1, \sum f.\text{backward\_packets})}$$

---

### 3. Packet Length Statistics
- **`mean_packet_length`**: Mean packet size across flows:
  $$\mu_L = \frac{1}{N_f} \sum_{f \in W} \frac{f.\text{byte\_count}}{f.\text{packet\_count}}$$
- **`packet_length_std`**: Standard deviation of packet sizes:
  $$\sigma_L = \sqrt{\frac{1}{N_f} \sum (L_i - \mu_L)^2}$$

---

### 4. TCP Flag Dynamics & Anomaly Ratios
- **`syn_rate`**: SYN packets received per second:
  $$\lambda_{\text{SYN}} = \frac{|\{f \in W \mid \text{SYN} \in f.\text{flags}\}|}{\Delta t}$$
- **`syn_ack_ratio`**: Half-open connection anomaly indicator:
  $$R_{\text{SYN/ACK}} = \frac{\text{Count}(\text{SYN})}{\max(1, \text{Count}(\text{ACK}))}$$
- **`rst_ratio`**: Teardown anomaly fraction:
  $$R_{\text{RST}} = \frac{\text{Count}(\text{RST})}{N_f}$$

---

### 5. Shannon Entropies
Measures statistical dispersion and randomness across source/destination IP addresses and ports:
$$H(X) = -\sum_{i=1}^{k} P(x_i) \log_2 P(x_i)$$
- **`entropy_source_ips`**: Low entropy indicates concentrated origin (e.g. focused DDoS), high entropy indicates botnet/distributed origin.
- **`entropy_dest_ports`**: Low entropy indicates single service targeting (e.g. HTTP flood), high entropy indicates horizontal/vertical port scanning.
- **`entropy_dest_ips`**: Dispersion over network perimeter assets.
- **`entropy_source_ports`**: Dispersion over ephemeral client ports.

---

### 6. Burstiness & Dynamics
- **`packet_rate_variance`**: $\text{Var}(\lambda_{p, f})$ across flows in window.
- **`byte_rate_variance`**: $\text{Var}(\lambda_{b, f})$ across flows in window.
- **`traffic_burst_score`**: Peak-to-average rate ratio:
  $$S_{\text{burst}} = \frac{\max_f(\lambda_{p, f})}{\bar{\lambda}_{p} + \epsilon}$$

---

### 7. Concentration & Connection Dynamics
- **`destination_concentration_score`**: Fraction of traffic targeting the most heavily visited destination IP:
  $$C_{\text{dst}} = \frac{\max_d \text{Count}(\text{dst}_d)}{N_f}$$
- **`repeated_destinations_ratio`**: Ratio of recurrent destination visits:
  $$R_{\text{rep}} = 1.0 - \frac{|\text{Unique Destinations}|}{N_f}$$
