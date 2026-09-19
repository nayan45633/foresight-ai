# Foresight AI — Security Architecture & Guidelines

## 1. Zero Hardcoded Secrets Policy
- All secrets, database URLs, token expiration parameters, and cryptographic signing keys are injected exclusively via environment variables (`pydantic-settings`).
- `.env.example` provides the exact schema and development defaults without exposing credentials.
- `.env` files are strictly excluded from version control via `.gitignore`.

## 2. Authentication & Authorization
- Passwords are encrypted using salted `bcrypt` algorithms.
- Authentication utilizes standard JSON Web Tokens (JWT) signed using `HS256` with strict expiration windows (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Role-based access control (RBAC) supports `admin`, `analyst`, and `observer` roles.

## 3. Defense-in-Depth HTTP Security Middleware
Every HTTP response is guarded by the following security headers:
- `X-Content-Type-Options: nosniff` — Prevents MIME-sniffing exploits.
- `X-Frame-Options: DENY` — Prevents clickjacking attacks.
- `X-XSS-Protection: 1; mode=block` — Cross-site scripting protection.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` — Enforces HTTPS.
- `Referrer-Policy: strict-origin-when-cross-origin` — Protects internal referrer leaks.
- `Permissions-Policy: geolocation=(), microphone=(), camera=()` — Disables unused browser hardware capabilities.

## 4. Input Validation & Telemetry Ingestion Guardrails
- Ingestion endpoints enforce strict payload bounds (maximum 5,000 flow records per batch).
- Pydantic models validate IPv4/IPv6 formats, port numbers ($0 \le port \le 65535$), and protocol enumerations.
