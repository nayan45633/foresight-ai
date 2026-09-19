"""Foresight AI - In-Memory Sliding Window Rate Limiting Middleware."""

import time
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Protects APIs from denial-of-service with an in-memory sliding window rate limiter."""

    def __init__(self, app, rate_limit_per_minute: int = 300, exempt_paths: Tuple[str, ...] = ("/api/v1/health", "/api/v1/ready", "/docs", "/openapi.json")):
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.exempt_paths = exempt_paths
        # Map client_ip -> list of timestamps
        self.requests_map: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0

        # Clean timestamps older than 60s
        timestamps = self.requests_map[client_ip]
        self.requests_map[client_ip] = [t for t in timestamps if t > window_start]
        current_count = len(self.requests_map[client_ip])

        if current_count >= self.rate_limit_per_minute:
            request_id = getattr(request.state, "request_id", "req-unknown")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit quota exceeded. Too many requests.",
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please retry after rate window resets.",
                        "request_id": request_id,
                        "details": {"limit_per_minute": self.rate_limit_per_minute, "retry_after_seconds": 60},
                    }
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.rate_limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60)),
                }
            )

        self.requests_map[client_ip].append(now)
        remaining = max(0, self.rate_limit_per_minute - (current_count + 1))

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))
        return response
