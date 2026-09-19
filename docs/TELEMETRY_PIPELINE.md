# Foresight AI — Telemetry Ingestion Pipeline

## 1. Overview
The **Foresight AI Telemetry Pipeline** transforms raw, heterogeneous, and untrusted network traffic captures into validated, deduplicated, bidirectional flow records and model-ready sliding temporal windows.

```mermaid
flowchart TD
    subgraph Sources ["1. Telemetry Sources"]
        A[PCAP / PCAPNG Files]
        B[NetFlow / IPFIX Streams]
        C[JSON Batch Records]
    end

    subgraph ValidationEngine ["2. Validation & Sanitization"]
        A --> D[PcapStreamParser]
        B --> E[Batch Validator]
        C --> E
        E --> F{Strict Validation}
        F -- Invalid / Out of Bounds --> G[Rejection Audit Log]
        F -- Valid Record --> H[Sanitized Record]
    end

    subgraph FlowEngine ["3. Flow Reconstruction & Dedup"]
        D --> I[Bidirectional Flow Reconstructor]
        H --> J[Deterministic Deduplicator]
        I --> J
        J --> K[Canonical FlowRecord]
    end

    subgraph TemporalEngine ["4. Feature & Temporal Windowing"]
        K --> L[Sliding Window Generator (60s/300s/900s)]
        L --> M[28-D Statistical Feature Extractor]
        M --> N[TemporalWindowFeatures]
        N --> O[Future Label Alignment (5m/15m/30m/60m)]
    end

    subgraph Storage ["5. Persistence & Delivery"]
        K --> P[(Network Flows DB)]
        N --> Q[(Temporal Windows DB)]
        K --> R[Live SOC Telemetry Hub]
    end
```

---

## 2. Ingestion Stages

### Stage 1: Ingestion & Adapter Normalization
- **PCAP Stream Parser** (`app/telemetry/pcap_parser.py`): Streams raw Ethernet / IP / TCP / UDP / ICMP frames through Scapy.
- **Batch Normalizer** (`app/telemetry/validation.py`): Parses JSON arrays with fallback field mapping.

### Stage 2: Strict Validation & Quality Tracking
- Verifies IPv4 and IPv6 syntax via `ipaddress`.
- Enforces strict port boundaries ($0 \le port \le 65535$).
- Rejects negative counters, `NaN`, and `Infinity`.
- Rejects impossible timestamps (pre-1970 or future clock drift $> 48$ hours).
- Records granular rejection codes (`INVALID_IP_ADDRESS`, `INVALID_PORT`, `NEGATIVE_OR_NON_FINITE_COUNTER`, `INVALID_TIMESTAMP`) for SOC observability.

### Stage 3: Bidirectional Flow Reconstruction
- Communicating endpoints $A \leftrightarrow B$ are merged into a single symmetric 5-tuple canonical key:
  $$\text{Key} = \min((IP_A, Port_A), (IP_B, Port_B)) \parallel \text{Protocol}$$
- Tracks directional forward/backward byte and packet counters:
  - `forward_packets`, `backward_packets`
  - `forward_bytes`, `backward_bytes`
  - TCP flags observed (`SYN`, `ACK`, `FIN`, `RST`, `PSH`, `URG`)
- Implements inactivity-based flow expiration (`idle_timeout_seconds=30s`, `active_timeout_seconds=120s`).

### Stage 4: Deterministic Deduplication
- Calculates SHA-256 fingerprint from canonical 5-tuple, 1-second timestamp bucket, packet/byte counts, and TCP flags.
- Enforces idempotent ingestion across repeat batches without losing legitimate repeated flows.

### Stage 5: Sliding Temporal Windows
- Aggregates chronological flow streams into overlapping sliding windows:
  - Size $\Delta t \in \{60s, 300s, 900s\}$
  - Stride $s \in \{30s, 60s\}$
- Guarantees zero future information leakage into past windows.
