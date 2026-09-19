# Foresight AI — AI-Based Network Attack Forecasting Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](https://www.typescriptlang.org/)
[![SIH 2026](https://img.shields.io/badge/SIH-2026-orange.svg)]()

> **Smart India Hackathon 2026**
> **Problem Statement:** AI-based Network Attack Forecasting from Network Traffic Data
> **Paradigm:** Reactive Detection $\rightarrow$ Proactive Temporal Attack Forecasting

---

## 🛡️ Executive Overview

Traditional Network Intrusion Detection Systems (NIDS) identify attacks **after** anomalous packets cross network perimeters (*"What is happening?"*). 

**Foresight AI** forecasts attack trajectories **before** they fully materialize (*"What is likely to happen in the next 5 to 60 minutes?"*). By continuously aggregating normalized network telemetry over sliding temporal windows, computing statistical dispersion and flag entropy, and evaluating calibrated probabilistic forecasters with quantified uncertainty, Foresight AI gives SOC analysts critical early-warning lead time.

---

## 🏗️ Architecture

```
RAW NETWORK TELEMETRY (NetFlow / IPFIX / PCAP / PCAPNG)
        ↓
STRICT VALIDATION & SANITIZATION (IPv4, IPv6, NaN checks)
        ↓
BIDIRECTIONAL FLOW RECONSTRUCTION & INACTIVITY TIMEOUTS
        ↓
DETERMINISTIC FLOW FINGERPRINTING & DEDUPLICATION
        ↓
28-D STATISTICAL BEHAVIOR FEATURES & SHANNON ENTROPY
        ↓
SLIDING TEMPORAL WINDOWS (60s, 300s, 900s)
        ↓
LEAKAGE-FREE MULTI-HORIZON TARGET ALIGNMENT (5m, 15m, 30m, 60m)
        ↓
TEMPORAL ML FORECASTING ENGINE (Step 3)
```

For comprehensive technical specifications, refer to:
- [`docs/TELEMETRY_PIPELINE.md`](docs/TELEMETRY_PIPELINE.md) *(NEW)*
- [`docs/FEATURE_ENGINEERING.md`](docs/FEATURE_ENGINEERING.md) *(NEW)*
- [`docs/PCAP_PROCESSING.md`](docs/PCAP_PROCESSING.md) *(NEW)*
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/TECH_STACK.md`](docs/TECH_STACK.md)
- [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)
- [`docs/ML_CONTRACT.md`](docs/ML_CONTRACT.md)
- [`docs/DATABASE.md`](docs/DATABASE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Docker (optional, for containerized run)

### 2. Environment Setup
```bash
# Clone repository and copy environment template
cp .env.example .env
```

### 3. Running the Backend API
```bash
# Activate virtual environment
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start FastAPI development server
cd backend
uvicorn app.main:app --reload --port 8000
```
- API Root: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/api/v1/docs`

### 4. Running the Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
- Web Interface: `http://localhost:3000`

---

## 🧪 Testing

```bash
# Run complete automated test suite (24 passing tests)
$env:PYTHONPATH="backend"
pytest -v backend/tests
```

---

## 📅 12-Step Implementation Roadmap

| Step | Milestone | Status |
|---|---|---|
| **Step 01** | **Foundation, Architecture & Engineering Setup** | **Complete** ✅ |
| **Step 02** | **Real Network Telemetry Ingestion Engine** | **Complete** ✅ |
| Step 03 | Core AI Forecasting Brain & Temporal ML Models | Next ⏳ |
| Step 04 | Multi-Horizon Dataset Construction & Preprocessing | Pending |
| Step 05 | Baseline Model Training & Hyperparameter Tuning | Pending |
| Step 06 | Probability Calibration (Platt/Isotonic/Brier Optimization) | Pending |
| Step 07 | Uncertainty Quantification Engine | Pending |
| Step 08 | SHAP & Feature Explainability Module | Pending |
| Step 09 | Early-Warning Proactive Alerting & Risk Engine | Pending |
| Step 10 | SOC Incident Management & Automated Playbooks | Pending |
| Step 11 | High-Density Glassmorphic SOC Command Center | Pending |
| Step 12 | End-to-End Evaluation, Performance Profiling & Demo Preparation | Pending |
