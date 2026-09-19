# Foresight AI — Production Deployment Handbook

This guide details the exact steps for deploying Foresight AI into production using:
- **Frontend**: Vercel (Next.js 14 App Router)
- **Backend API**: Render (FastAPI on Python 3.13)
- **Database**: Managed PostgreSQL (Render PostgreSQL / Neon / AWS RDS)
- **Caching / Rate-Limiting**: Managed Redis (Optional for distributed clusters)

---

## 1. Production Architecture Overview

```
                        ┌───────────────────────────────┐
                        │   Operator Browser / SOC UI   │
                        └───────────────┬───────────────┘
                                        │ (HTTPS)
                                        ▼
                        ┌───────────────────────────────┐
                        │   Vercel Next.js 14 Edge CDN  │
                        └───────────────┬───────────────┘
                                        │ (HTTPS / CORS / Bearer JWT)
                                        ▼
                        ┌───────────────────────────────┐
                        │   Render FastAPI Application  │
                        └───────┬───────────────┬───────┘
                                │               │
                ┌───────────────┘               └───────────────┐
                ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│  Managed PostgreSQL Database  │               │   Model Artifacts (Local/EFS) │
│ (13 Tables, Alembic Migrated) │               │   (SHA-256 Checksum Verified) │
└───────────────────────────────┘               └───────────────────────────────┘
```

---

## 2. Backend Deployment on Render

### Step 2.1: Create Managed PostgreSQL on Render
1. In the Render Dashboard, create a **New PostgreSQL Database**.
2. Set Database Name: `foresight_production_db`.
3. Set User: `foresight_admin`.
4. Copy the **Internal Database URL** (e.g. `postgresql+asyncpg://foresight_admin:PASSWORD@dpg-xxxx:5432/foresight_production_db`).

### Step 2.2: Create Web Service on Render
1. Create a **New Web Service** linked to the GitHub repository.
2. Root Directory: `backend`
3. Environment: `Python 3`
4. Build Command: `pip install --upgrade pip && pip install -r requirements.txt && python -m alembic upgrade head`
5. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Health Check Path: `/api/v1/health`

### Step 2.3: Render Environment Variables
Configure the following in the Render dashboard:
- `ENVIRONMENT`: `production`
- `DATABASE_URL`: `postgresql+asyncpg://foresight_admin:PASSWORD@dpg-xxxx:5432/foresight_production_db`
- `SECRET_KEY`: `<Generate 64-character cryptographically random secret>`
- `BACKEND_CORS_ORIGINS`: `["https://foresight-ai.vercel.app"]`
- `LOG_LEVEL`: `INFO`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: `15`
- `REFRESH_TOKEN_EXPIRE_DAYS`: `7`
- `CONFORMAL_TARGET_COVERAGE`: `0.90`

---

## 3. Frontend Deployment on Vercel

### Step 3.1: Connect Project on Vercel
1. Import the Git repository in Vercel.
2. Root Directory: `frontend`
3. Framework Preset: `Next.js`
4. Build Command: `npm run build`
5. Output Directory: `.next`

### Step 3.2: Vercel Environment Variables
- `NEXT_PUBLIC_API_URL`: `https://foresight-api.onrender.com/api/v1`

---

## 4. Post-Deployment Verification (Smoke Tests)

Once live credentials are configured and deployment triggers complete, run the following smoke tests:

1. **Liveness & Readiness**:
   ```bash
   curl -s https://foresight-api.onrender.com/api/v1/health | jq .
   curl -s https://foresight-api.onrender.com/api/v1/ready | jq .
   ```
2. **Interactive OpenAPI Specs**:
   - Access: `https://foresight-api.onrender.com/api/v1/docs`
3. **Frontend SOC Dashboard**:
   - Access: `https://foresight-ai.vercel.app`
   - Test Login, Overview, Forecast Timeline, Telemetry Hub, Risk Graph, Explainability, What-If Studio, and System Health.
