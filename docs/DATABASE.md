# Foresight AI — Database Architecture & Entity Specifications

## 1. Relational Schema Design

```mermaid
erDiagram
    USERS ||--o{ AUDIT_LOGS : performs
    TELEMETRY_BATCHES ||--o{ NETWORK_FLOWS : contains
    FORECAST_WINDOWS ||--o{ ATTACK_FORECASTS : feeds
    ATTACK_FORECASTS ||--o{ SECURITY_ALERTS : triggers
    SECURITY_ALERTS ||--o{ INCIDENT_CASES : escalates
    MODEL_VERSIONS ||--o{ ATTACK_FORECASTS : generates

    USERS {
        string id PK
        string email UK
        string username UK
        string hashed_password
        string role
        boolean is_active
    }

    NETWORK_FLOWS {
        string id PK
        datetime timestamp
        string source_ip
        string destination_ip
        int source_port
        int destination_port
        string protocol
        float flow_duration_ms
        bigint packet_count
        bigint byte_count
        string tcp_flags
    }

    ATTACK_FORECASTS {
        string id PK
        datetime forecast_timestamp
        int horizon_minutes
        string predicted_threat
        float probability
        float confidence
        float anomaly_score
        string risk_level
        json uncertainty_metrics
        string model_version
        json feature_contributions
    }

    SECURITY_ALERTS {
        string id PK
        string title
        string severity
        string status
        string predicted_threat
        int estimated_time_to_impact_minutes
        string recommended_mitigation
    }
```

---

## 2. Table Indexing & Query Optimizations
- `network_flows`: Composite index on `(timestamp, source_ip, destination_ip)` and `(destination_port, protocol)` for temporal sliding window slicing.
- `attack_forecasts`: Index on `(forecast_timestamp, predicted_threat)` and `(risk_level, horizon_minutes)` for real-time SOC alerting.
- `audit_logs`: Index on `(action, created_at)` for compliance tracking.
