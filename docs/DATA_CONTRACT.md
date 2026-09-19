# Foresight AI — Telemetry & Flow Data Contracts

## 1. Internal Normalized Flow Schema (`FlowRecord`)

The core internal representation for all network telemetry:

| Field Name | Type | Description |
|---|---|---|
| `id` | `string` | Deterministic flow fingerprint or UUID. |
| `timestamp` | `datetime` (UTC) | Start time of connection/flow. |
| `end_timestamp` | `datetime` (UTC) | End time of connection/flow. |
| `source_ip` | `string` (IPv4/IPv6) | Origin IP address. |
| `destination_ip` | `string` (IPv4/IPv6) | Target IP address. |
| `source_port` | `integer` ($0 \dots 65535$) | Origin transport layer port. |
| `destination_port` | `integer` ($0 \dots 65535$) | Destination transport layer port. |
| `protocol` | `enum` | Transport protocol (`TCP`, `UDP`, `ICMP`, `GRE`, `OTHER`). |
| `flow_duration_ms`| `float` | Duration of connection in milliseconds. |
| `packet_count` | `integer` | Total packet volume ($N_p$). |
| `byte_count` | `integer` | Total payload and header byte volume ($N_b$). |
| `forward_packets` | `integer` | Packets transmitted initiator $\rightarrow$ responder. |
| `backward_packets`| `integer` | Packets transmitted responder $\rightarrow$ initiator. |
| `forward_bytes` | `integer` | Bytes transmitted initiator $\rightarrow$ responder. |
| `backward_bytes` | `integer` | Bytes transmitted responder $\rightarrow$ initiator. |
| `packet_rate` | `float` | Packets transmitted per second. |
| `byte_rate` | `float` | Bytes transmitted per second. |
| `tcp_flags` | `string` | Concatenated flags observed (`SYN`, `ACK`, `FIN`, `RST`, `PSH`, `URG`). |
| `connection_state`| `string` | Protocol state (`ESTABLISHED`, `CLOSED`, `RESET`, `UNKNOWN`). |
| `direction` | `enum` | Traffic direction (`ingress`, `egress`, `internal`). |
| `metadata` | `object` (JSON) | Sensor, VLAN, and bidirectional metadata. |

---

## 2. Sliding Temporal Window Features (`TemporalWindowFeatures`)

Dense 28-dimensional mathematical vector computed over sliding time slices:

| Index | Feature Name | Description |
|---|---|---|
| 0 | `flow_volume` | Total flows in window |
| 1 | `packet_volume` | Total packets in window |
| 2 | `byte_volume` | Total bytes in window |
| 3 | `packets_per_second` | Volumetric packet rate |
| 4 | `bytes_per_second` | Volumetric byte rate |
| 5 | `mean_flow_duration_ms` | Mean connection duration |
| 6 | `duration_variance` | Variance of connection durations |
| 7 | `forward_packets_total` | Total forward packets |
| 8 | `backward_packets_total` | Total backward packets |
| 9 | `forward_bytes_total` | Total forward bytes |
| 10 | `backward_bytes_total` | Total backward bytes |
| 11 | `forward_backward_ratio` | Directional traffic symmetry ratio |
| 12 | `mean_packet_length` | Mean packet byte length |
| 13 | `packet_length_std` | Standard deviation of packet byte length |
| 14 | `syn_count` | Count of SYN flagged flows |
| 15 | `syn_rate` | SYN arrival rate per second |
| 16 | `ack_count` | Count of ACK flagged flows |
| 17 | `rst_count` | Count of RST flagged flows |
| 18 | `syn_ack_ratio` | Half-open SYN flood indicator |
| 19 | `rst_ratio` | Teardown anomaly ratio |
| 20 | `unique_source_ips` | Cardinality of source IP set |
| 21 | `unique_destination_ips` | Cardinality of destination IP set |
| 22 | `unique_source_ports` | Cardinality of source port set |
| 23 | `unique_destination_ports`| Cardinality of destination port set |
| 24 | `entropy_source_ips` | Shannon entropy of source IP distribution |
| 25 | `entropy_dest_ips` | Shannon entropy of destination IP distribution |
| 26 | `entropy_source_ports` | Shannon entropy of source port distribution |
| 27 | `entropy_dest_ports` | Shannon entropy of destination port distribution |

---

## 3. Future Horizon Target Contract (`FutureHorizonTarget`)

Used for supervised multi-horizon forecasting targets ($t + 5m, t + 15m, t + 30m, t + 60m$), preventing temporal leakage into past windows:

```json
{
  "window_id": "win-9a8b7c6d-5e4f",
  "target_timestamp": "2026-09-18T20:30:00.000Z",
  "horizon_5m_threat": "BENIGN",
  "horizon_5m_attack_occurred": false,
  "horizon_15m_threat": "Distributed Denial of Service",
  "horizon_15m_attack_occurred": true,
  "horizon_30m_threat": "Distributed Denial of Service",
  "horizon_30m_attack_occurred": true,
  "horizon_60m_threat": "Distributed Denial of Service",
  "horizon_60m_attack_occurred": true
}
```
