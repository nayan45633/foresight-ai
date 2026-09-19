# Foresight AI — Production Configuration & Environment Guide

This document details all configuration parameters, environment variables, security constraints, and database pooling configurations for production deployments.

---

## 1. Environment Variable Reference

### Backend Configuration (`backend/.env`)

| Variable | Type | Default / Example | Required in Production | Description |
| :--- | :---: | :--- | :---: | :--- |
| `ENVIRONMENT` | String | `production` | Yes | Environment mode (`development`, `staging`, `production`). Disables debug endpoints when `production`. |
| `PROJECT_NAME` | String | `Foresight AI` | No | Display name for API logs and metadata. |
| `PORT` | Integer | `8000` | Yes (Cloud) | Host port provided dynamically by platforms like Render (`$PORT`). |
| `DATABASE_URL` | String | `postgresql+asyncpg://...` | Yes | SQLAlchemy 2.0 Async connection string (PostgreSQL with `asyncpg`). |
| `SECRET_KEY` | String | `(64-char random hex)` | Yes | Secret key used for HS256 JWT signature verification. |
| `ALGORITHM` | String | `HS256` | No | Cryptographic algorithm for JWT encoding. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Integer | `15` | No | Expiration window for access tokens. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Integer | `7` | No | Expiration window for long-lived refresh tokens. |
| `BACKEND_CORS_ORIGINS` | JSON Array / String | `["https://foresight.vercel.app"]` | Yes | Explicit whitelist of allowed frontend origins for CORS. |
| `LOG_LEVEL` | String | `INFO` | No | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `RATE_LIMIT_PER_MINUTE` | Integer | `300` | No | In-memory sliding window rate limit threshold per client IP. |
| `MAX_PCAP_UPLOAD_BYTES` | Integer | `52428800` (50MB) | No | Maximum permitted file upload size for PCAP streams. |
| `CONFORMAL_TARGET_COVERAGE` | Float | `0.90` | No | Nominal coverage guarantee for split-conformal prediction intervals ($1-\alpha$). |

### Frontend Configuration (`frontend/.env.production`)

| Variable | Type | Default / Example | Required | Description |
| :--- | :---: | :--- | :---: | :--- |
| `NEXT_PUBLIC_API_URL` | String | `https://foresight-api.onrender.com/api/v1` | Yes | Base URL pointing to the deployed backend FastAPI service. |

---

## 2. Production Security Hardening Checklist

1. **No Wildcard CORS in Production**: Ensure `BACKEND_CORS_ORIGINS` contains only trusted frontend domains.
2. **Database Connection Pooling**:
   - `pool_size`: 10
   - `max_overflow`: 20
   - `pool_timeout`: 30s
   - `pool_recycle`: 1800s (prevents stale database connections)
3. **Automated Schema Migrations**: Execute `python -m alembic upgrade head` as part of the container build / deploy pipeline before booting the HTTP worker processes.
4. **Artifact Read-Only Mounting**: Ensure the `artifacts/` folder containing serialized models and calibrators has read-only filesystem permissions in production containers.
