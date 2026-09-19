# Foresight AI — API Specification Reference

All endpoints are served under the root prefix `/api/v1`.

## 1. System Health & Probes
- `GET /health` — Service liveness probe.
- `GET /ready` — Database and subsystem readiness probe.

## 2. Authentication & Identity
- `POST /auth/register` — Registers a new user account with salted password hashing.
- `POST /auth/login` — Authenticates credentials and issues signed JWT bearer token.
- `POST /auth/logout` — Revokes client-side token session.
- `GET /auth/me` — Retrieves current authenticated user profile.

## 3. Network Telemetry Ingestion (Step 2 Engine)
- `POST /telemetry/flows` — Ingests a batch of normalized `FlowRecord` objects with deduplication.
- `POST /telemetry/flows/batch` — Validates, sanitizes, and ingests raw heterogeneous JSON records.
- `POST /telemetry/pcap` — Uploads a `.pcap` / `.pcapng` capture file for asynchronous packet streaming and flow reconstruction.
- `GET /telemetry/ingestion/{job_id}` — Queries PCAP ingestion job status, progress, and generated flow metrics.
- `GET /telemetry/recent` — Fetches latest ingested flows with optional protocol and IP filtering.
- `GET /telemetry/statistics` — Real-time flow volume, rate, protocol breakdown, and unique host counts.
- `GET /telemetry/quality` — Telemetry data quality report (acceptance rate, duplicate counts, rejection reason breakdown).
- `GET /telemetry/windows` — Generates sliding temporal windows with extracted 28-D behavior features.

## 4. Attack Forecasting
- `GET /forecast/current` — Retrieves the latest generated attack forecast.
- `GET /forecast/multi-horizon` — Multi-horizon predictions (5m, 15m, 30m, 60m).
- `GET /forecast/history` — Historical predictions with optional severity filtering.
- `GET /forecast/{id}` — Specific forecast by ID with full explainability attribution.

## 5. Security Alerts & Proactive Remediation
- `GET /alerts` — List open and historical alerts.
- `GET /alerts/{id}` — Detailed alert with suggested mitigation actions.
- `PATCH /alerts/{id}` — Update alert status (`OPEN`, `INVESTIGATING`, `MITIGATED`, `FALSE_POSITIVE`).

## 6. SOC Incident Investigations
- `GET /incidents` — List active incident investigation cases.
- `POST /incidents` — Create new incident case.
- `GET /incidents/{id}` — Full IOC details and event timeline.

## 7. Model Registry & Calibration
- `GET /model/status` — Currently active forecasting model metadata and parameters.
- `GET /model/calibration` — Brier score, Expected Calibration Error (ECE), and reliability bins.
