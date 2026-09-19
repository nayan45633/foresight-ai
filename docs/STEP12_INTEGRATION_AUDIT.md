# Foresight AI — Step 12 Integration & Architecture Audit

This document maps all frontend SOC dashboard views to backend API endpoints, database persistence entities, and underlying machine learning engines to verify architectural consistency across Steps 1–11.

---

## 1. System Integration Architecture

```
[ Operator Browser / SOC Workstation ]
                    │
                    ▼ (HTTPS / TLS 1.3)
      [ Vercel Next.js 14 Frontend ]
                    │
                    ▼ (JWT Bearer / CORS)
      [ Render FastAPI Python Backend ]
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
[ Managed DB ] [ ML Pipeline ] [ Observability ]
 (PostgreSQL)  (HGB/SHAP/Conf) (Drift/Quality)
```

---

## 2. Frontend View to Backend API Mapping Matrix

| Frontend Page / Component | Primary Backend API Endpoints | HTTP Method | DB Models Involved | ML & Analytics Engines | Status |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **Overview (Command Center)**<br>`CommandCenterOverview.tsx` | `/api/v1/risk/current`<br>`/api/v1/model/forecast/timeline`<br>`/api/v1/telemetry/quality`<br>`/api/v1/telemetry/statistics` | `GET` | `RiskStateRecord`<br>`NetworkFlow`<br>`TelemetryBatch` | Multi-Horizon GBM (+5m..+60m)<br>Isotonic Calibrators<br>Risk State Machine | ✅ Verified |
| **Forecast (Multi-Horizon Timeline)**<br>`ForecastTimeline.tsx` | `/api/v1/model/forecast/timeline`<br>`/api/v1/model/lead-time`<br>`/api/v1/model/calibration` | `GET` | `AttackForecast`<br>`ModelVersionRecord` | HistGradientBoosting (4 Horizons)<br>Split-Conformal Predictor<br>Empirical Lead-Time Engine | ✅ Verified |
| **Telemetry (Live Ingestion Hub)**<br>`TelemetryHub.tsx` | `/api/v1/telemetry/quality`<br>`/api/v1/telemetry/statistics`<br>`/api/v1/telemetry/recent`<br>`/api/v1/telemetry/windows`<br>`/api/v1/telemetry/pcap` | `GET`<br>`POST` | `NetworkFlow`<br>`TelemetryBatch`<br>`TelemetryJob`<br>`TemporalWindow` | PcapStreamParser<br>Bidirectional Flow Reconstructor<br>37-Feature Extractor | ✅ Verified |
| **Risk (Risk State & Attack Path)**<br>`RiskStateView.tsx` | `/api/v1/risk/current`<br>`/api/v1/risk/timeline`<br>`/api/v1/risk/attack-path`<br>`/api/v1/risk/transitions` | `GET` | `RiskStateRecord`<br>`RiskTransitionRecord` | 4-State Hysteresis Machine<br>Attack Path Transition Graph<br>Topological Traversal | ✅ Verified |
| **Explainability (SHAP Studio)**<br>`ExplainabilityView.tsx` | `/api/v1/model/explain`<br>`/api/v1/model/explain/global` | `GET`<br>`POST` | `ModelVersionRecord` | TreeSHAP Explainer<br>Local Additive Attributions<br>37-Feature Global Matrix | ✅ Verified |
| **What-If (Counterfactual Studio)**<br>`CounterfactualStudio.tsx` | `/api/v1/model/counterfactual/catalog`<br>`/api/v1/model/counterfactual/presets`<br>`/api/v1/model/counterfactual/evaluate`<br>`/api/v1/model/counterfactual/history` | `GET`<br>`POST` | `CounterfactualScenarioRecord` | Counterfactual Perturbation Engine<br>Multi-Horizon Re-Inference<br>TreeSHAP Differential Analysis | ✅ Verified |
| **System (Health & Observability)**<br>`SystemHealthView.tsx` | `/api/v1/health`<br>`/api/v1/ready`<br>`/api/v1/model/versions`<br>`/api/v1/model/current`<br>`/api/v1/monitoring/health`<br>`/api/v1/monitoring/data-quality`<br>`/api/v1/monitoring/drift`<br>`/api/v1/monitoring/calibration`<br>`/api/v1/monitoring/performance`<br>`/api/v1/audit/logs` | `GET` | `ModelVersionRecord`<br>`AuditLog`<br>`AuthSession` | Artifact SHA-256 Checksum Guard<br>PSI & KS Drift Monitor<br>ECE Calibration Monitor<br>Per-Horizon Performance Engine | ✅ Verified |
| **Authentication & RBAC**<br>`AuthModal.tsx` & `AuthContext.tsx` | `/api/v1/auth/register`<br>`/api/v1/auth/login`<br>`/api/v1/auth/refresh`<br>`/api/v1/auth/logout`<br>`/api/v1/auth/me`<br>`/api/v1/auth/users` | `POST`<br>`GET` | `User`<br>`AuthSession`<br>`AuditLog` | Salted bcrypt (12 rounds)<br>Single-Use Refresh Token Rotation<br>Server-Side RoleChecker (RBAC) | ✅ Verified |

---

## 3. Consistency & Integrity Findings

1. **Strict Horizon Isolation**: Throughout all database models (`AttackForecast`), ML contracts (`HorizonForecastIntelligence`), API schemas, and frontend view states, the four discrete lookahead horizons (+5m, +15m, +30m, +60m) remain completely segregated without inter-horizon contamination or averaging.
2. **Honest Data States**: When external telemetry or verified ground-truth labels are absent, the entire system responds with truthful empty states (`AWAITING TELEMETRY`, `AWAITING GROUND TRUTH`, `INSUFFICIENT DATA`, `INSUFFICIENT EMPIRICAL EVIDENCE`, `NO REFERENCE WINDOW`) without generating mock fallbacks.
3. **Persisted Tenancy & IDOR Isolation**: All database operations for scenarios, jobs, and audit events verify user ownership before fulfilling queries.
