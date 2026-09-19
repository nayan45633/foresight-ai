"""Foresight AI - Request Tracing and Performance Logging Middleware."""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.logging import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Injects a unique request ID into every request, records duration, and logs structured access."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
            
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)",
                extra={
                    "request_id": request_id,
                    "client_ip": request.client.host if request.client else "unknown",
                    "duration_ms": round(duration_ms, 2),
                }
            )
            return response
            
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path}: {str(exc)}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "client_ip": request.client.host if request.client else "unknown",
                    "duration_ms": round(duration_ms, 2),
                }
            )
            raise exc
