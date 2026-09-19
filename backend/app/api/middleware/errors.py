"""Foresight AI - Structured Error Handlers and Formatter."""

import uuid
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.logging import logger


def setup_exception_handlers(app: FastAPI) -> None:
    """Registers centralized structured exception handlers."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        error_code = f"HTTP_{exc.status_code}"
        if exc.status_code == 401:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            error_code = "FORBIDDEN"
        elif exc.status_code == 404:
            error_code = "NOT_FOUND"
        elif exc.status_code == 409:
            error_code = "CONFLICT"
        elif exc.status_code == 422:
            error_code = "UNPROCESSABLE_ENTITY"
        elif exc.status_code == 503:
            error_code = "SERVICE_UNAVAILABLE"

        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": exc.detail,
                "error": {
                    "code": error_code,
                    "message": str(exc.detail),
                    "request_id": request_id,
                    "details": None,
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Serialize validation errors safely
        errors = []
        for err in exc.errors():
            clean_err = {
                "loc": [str(loc) for loc in err.get("loc", [])],
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            errors.append(clean_err)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": errors,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload schema.",
                    "request_id": request_id,
                    "details": errors,
                }
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(
            f"Unhandled server exception [Request-ID: {request_id}] on {request.method} {request.url.path}: {exc}",
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error. Please contact SOC operations.",
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the request.",
                    "request_id": request_id,
                    "details": None,
                }
            }
        )
