# Foresight AI — Security Threat Model

This document establishes the comprehensive threat model for the Foresight AI cybersecurity forecasting platform. It identifies attack surfaces, threat vectors, mitigations, remaining risks, and automated test verifications.

---

## 1. System Overview & Trust Boundaries

```
[ External Sensor / TAP / Operator Browser ]
                     │  (HTTPS / TLS 1.3)
                     ▼
             [ API Gateway / CDN ]
                     │  (WAF / Reverse Proxy)
                     ▼
          [ FastAPI Backend Application ]
   ┌─────────────────┼─────────────────┐
   ▼                 ▼                 ▼
[ SQLite/PostgreSQL ] [ ML Artifacts ] [ Telemetry / Temp ]
```

### Trust Boundaries:
1. **Unauthenticated Boundary**: External internet / untrusted clients to FastAPI public endpoints (`/api/v1/auth/login`, `/api/v1/health`, `/api/v1/ready`).
2. **Authenticated Operator Boundary**: Validated JWT bearer token to operator endpoints, segregated by RBAC (`USER`, `ANALYST`, `ADMIN`).
3. **Data Ingestion Boundary**: Network packet capture (PCAP) and flow streams entering ingestion parsers and normalizers.
4. **Machine Learning Boundary**: Raw features entering TreeSHAP, XGBoost/LightGBM multi-horizon forecasters, Isotonic calibrators, and Conformal predictor sets.
5. **Storage & Persistence Boundary**: SQL queries to PostgreSQL / SQLite, and local disk access for serialized model artifacts (`.joblib`, `.json`).

---

## 2. Comprehensive Threat Analysis Matrix

| Threat Category | Threat Vector | Attack Surface | Mitigation Implemented | Remaining Risk | Automated Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Authentication** | Credential Stuffing / Brute Force | `POST /api/v1/auth/login` | Salted bcrypt hashing (cost factor 12), rate limiting (300 req/min/IP), constant-time verification behavior. | Distributed botnet attacks bypassing single-IP rate limits if behind non-propagating proxy. | `tests/test_step11_security_threats.py::test_auth_brute_force_protection` |
| **Authentication** | Refresh Token Replay / Theft | `POST /api/v1/auth/refresh` | Single-use refresh token rotation; token hashing (SHA-256) in `auth_sessions`; immediate session revocation on rotation or detected reuse. | Time-of-check to time-of-use race condition if concurrent requests occur in sub-millisecond window. | `tests/test_step11_security_threats.py::test_refresh_token_replay_rejected` |
| **Authentication** | Session Fixation / Hijacking | JWT Bearer & Session IDs | Cryptographically random `jti` (UUID4) in access tokens; access token lifespan capped at 15 minutes; refresh token tied to client session. | Local device compromise where active memory is read. | `tests/test_step9_auth_and_rbac.py::test_token_lifecycle` |
| **Authentication** | Expired / Malformed JWT Usage | All protected endpoints | Strict cryptographic signature validation, `exp` expiration verification, algorithm whitelist (`HS256`). | Key rotation window during active secret transition. | `tests/test_step11_security_threats.py::test_invalid_and_expired_jwt_rejected` |
| **Authorization (RBAC)** | Privilege Escalation | `POST /api/v1/model/versions`, `GET /api/v1/auth/users` | Authoritative server-side `RoleChecker` enforcing `ADMIN` on model mutations and `ANALYST`/`ADMIN` on audit logs. | Misconfigured role assignment by authorized admin. | `tests/test_step9_auth_and_rbac.py::test_rbac_access_matrix` |
| **Authorization (IDOR)** | Insecure Direct Object Reference | `/telemetry/ingestion/{job_id}`, `/model/counterfactual/{id}` | Object-level tenancy checks verifying `user_id` matches the authenticated actor, returning 403/404 on unauthorized cross-tenant queries. | Public unauthenticated PCAP submissions without user binding rely on job UUID entropy. | `tests/test_step11_security_threats.py::test_idor_cross_tenant_isolation` |
| **Rate Limiting** | Denial of Service / Resource Exhaustion | All API Endpoints | Sliding window rate limiter injecting standard rate headers (`X-RateLimit-*`) and returning HTTP 429 when limits exceeded. | In-memory limiter is per-process; multi-worker clustering requires shared Redis state. | `tests/test_step9_security_and_api_hardening.py::test_rate_limiting_enforcement` |
| **Telemetry Ingestion** | Malformed / Corrupt PCAP Exploits | `POST /api/v1/telemetry/pcap` | Pre-validation of PCAP headers, Scapy safe dissection with max packet caps, strict try/except blocks setting job to `FAILED`. | Zero-day vulnerabilities in underlying C-based pcap libraries if native extensions are used. | `tests/test_step11_telemetry_and_ml_security.py::test_malformed_pcap_safe_rejection` |
| **Telemetry Ingestion** | Oversized Payload / Memory Bomb | `POST /api/v1/telemetry/flows`, `/pcap` | Request body length validation (max 50MB for PCAP, max 5,000 flows per JSON batch), streaming disk write with immediate unlink in `finally`. | Disk saturation if tmp directory disk quota is unmonitored. | `tests/test_step11_telemetry_and_ml_security.py::test_oversized_telemetry_rejected` |
| **Telemetry Ingestion** | Numeric Anomalies (NaN/Inf/-Values) | Ingestion Normalizer | Explicit range assertions: reject negative byte/packet counts, sanitize/filter NaN/Infinity values, clamp timestamp offsets. | Synthetic adversarial noise designed to mimic valid statistical distributions. | `tests/test_step11_telemetry_and_ml_security.py::test_numeric_anomalies_rejected` |
| **ML Input Security** | Adversarial Feature Injection | `POST /api/v1/forecast/predict`, `/model/counterfactual` | Authoritative 37-feature schema enforcement with exact order, type checking, and dimension validation ($D = 37$). | Black-box gradient-based adversarial perturbations within valid numeric bounds. | `tests/test_step11_telemetry_and_ml_security.py::test_ml_feature_schema_strictness` |
| **Model Integrity** | Model Artifact Tampering / Poisoning | Local File Storage / Model Registry | SHA-256 checksum verification against registered manifest upon artifact load; system fails closed on mismatch. | Compromise of file system and manifest metadata simultaneously by root attacker. | `tests/test_step11_telemetry_and_ml_security.py::test_model_artifact_tamper_fails_closed` |
| **Model Registry** | Path Traversal / File Inclusion | `POST /api/v1/model/versions/{tag}/activate` | Strict regex validation (`^[a-zA-Z0-9._-]+$`) on model tags; paths resolved strictly within sandboxed `artifacts/` directory; no user-supplied paths. | Symlink attacks if the artifact directory is mounted to an untrusted shared host volume. | `tests/test_step11_security_threats.py::test_model_registry_path_traversal_blocked` |
| **Injection** | SQL Injection | Database Queries | 100% parameterized queries via SQLAlchemy 2.0 Async ORM with zero raw string concatenation. | Bugs within third-party database dialect drivers. | `tests/test_step11_security_threats.py::test_sql_injection_resilience` |
| **Cross-Site Attacks** | XSS & Clickjacking | Web Responses | Defensive HTTP headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, strict React JSX escaping). | DOM-based XSS if third-party NPM libraries bypass React rendering. | `tests/test_step9_security_and_api_hardening.py::test_security_headers_present` |
| **Audit & Logging** | Credential / Secret Leakage | Log Streams & Error Messages | Centralized logging filter stripping `password`, `token`, `authorization`, `secret`; structured error handlers masking internal stack traces. | Accidental logging of sensitive payload keys not matching the regex redact filter. | `tests/test_step11_security_threats.py::test_error_handling_masks_sensitive_internals` |

---

## 3. Deployment Security Recommendations

1. **Single-Instance vs. Distributed Rate Limiting**: The current sliding window rate limiter runs in-process memory. In multi-pod production Kubernetes deployments, configure Redis as the shared backend.
2. **Artifact Volume Isolation**: Mount the ML model artifacts directory as read-only (`ro`) in Docker containers.
3. **TLS Termination**: Terminate TLS 1.3 at the reverse proxy/ingress with HSTS enabled (`Strict-Transport-Security: max-age=31536000; includeSubDomains`).
