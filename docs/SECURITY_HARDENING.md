# Foresight AI — Security & Resilience Hardening

This document summarizes the technical security controls, API hardening configurations, and operational resilience measures implemented across Foresight AI.

---

## 1. Authentication & Session Architecture

- **Password Storage**: Passwords hashed with standard bcrypt (12 rounds) with explicit 72-byte truncation protection.
- **JWT Signing**: HS256 algorithm with 256-bit cryptographic secrets. Tokens contain unique `jti` nonces and short expiration windows (15 minutes).
- **Session Revocation**: Stored in `auth_sessions` table with SHA-256 token hashing, `is_revoked` boolean flags, and client IP/user-agent tracking.
- **Refresh Token Rotation**: Each invocation of `POST /api/v1/auth/refresh` invalidates the prior session, issues a new single-use refresh token, and logs the rotation event. Detected reuse of old refresh tokens immediately flags potential session theft and terminates the session family.

---

## 2. Server-Side RBAC & Tenancy Isolation

- **Role Hierarchy**: `USER` < `ANALYST` < `ADMIN`.
- **Authoritative Authorization**: Frontend controls hide inaccessible buttons for UX, but all security policies are strictly enforced server-side via FastAPI dependencies (`RoleChecker` and user-ownership queries).
- **IDOR Protection**: Ingestion jobs, historical what-if scenarios, and session revocation queries explicitly verify that `resource.user_id == current_user.id` (unless the requester has `ADMIN` privileges).

---

## 3. Defense-in-Depth API Protections

- **Structured Error Responses**: All exceptions (400, 401, 403, 404, 409, 422, 429, 500) return normalized JSON error payloads containing `code`, `message`, and `request_id`. Internal database errors or stack traces are never exposed to clients.
- **HTTP Security Headers**: Injected into all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Rate Limiting**: Sliding-window rate limiter per client IP with standard `X-RateLimit-*` response headers.
- **Input Sanitization**: Authoritative 37-feature ML schema validation, PCAP payload size limits (50MB), and regex validation on model tags (`^[a-zA-Z0-9._-]+$`).

---

## 4. Failure Recovery & Safe Defaults

- **Fail-Closed Model Loading**: If an artifact checksum fails, the system logs a critical security alert, refuses to serve unverified weights, and reports `CRITICAL` model health.
- **Database Disconnection Recovery**: Async connection pooling automatically retries transient disconnects and surfaces clean 503 Service Unavailable responses rather than corrupting in-flight transactions.
- **Temporary File Lifecycle**: PCAP uploads written to temporary disk storage are guaranteed to be unlinked in `finally` blocks, preventing local disk exhaustion attacks.
