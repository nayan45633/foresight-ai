# Foresight AI — Technology Stack & Engineering Decisions

## Technology Choices & Rationale

| Domain | Technology Selected | Rationale & Trade-offs |
|---|---|---|
| **Backend Framework** | **Python 3.13 + FastAPI** | Native integration with ML ecosystems (NumPy, SciPy, scikit-learn), high-throughput asynchronous request handling via `uvloop`/Starlette, automatic OpenAPI 3.1 generation, and strict typing with Pydantic v2. |
| **Frontend Framework** | **Next.js 14 (App Router) + React 18** | Industry standard for rich dashboards, high performance server/client component separation, robust TypeScript typing, and responsive spatial SOC interfaces. |
| **Styling & Design System** | **Tailwind CSS + Glassmorphism Tokens** | Bespoke dark cybersecurity aesthetic ("Apple Liquid Glass" meets SOC command center) without bloated heavy UI dependencies. |
| **Database & ORM** | **SQLAlchemy 2.0 (Async) + PostgreSQL / SQLite** | Asynchronous ORM supporting zero-friction local SQLite testing and high-concurrency production PostgreSQL with connection pooling. |
| **Data Validation & Contracts** | **Pydantic v2** | Rust-backed blazing fast schema validation enforcing strict data contracts across all pipeline stages. |
| **Authentication & Crypto** | **PyJWT + Bcrypt (Passlib)** | Stateless, standard JWT bearer token authentication with cryptographically salted hashes. |
| **Containerization** | **Docker & Docker Compose** | Reproducible multi-service deployment orchestrating backend, frontend, database, and cache. |
| **Testing** | **pytest + pytest-asyncio + httpx** | Modern async-first testing suite for complete unit and integration test coverage. |
