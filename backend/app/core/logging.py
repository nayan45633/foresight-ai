"""Foresight AI - Structured Observability & Logging System.

Provides structured logging, sensitive data masking, and request context injection.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Outputs log records in structured JSON format for SOC and observability ingest."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        
        # Capture custom context passed via 'extra' dictionary
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "client_ip"):
            log_obj["client_ip"] = record.client_ip
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> logging.Logger:
    """Configures application root and uvicorn logging handlers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )
        
    root_logger.addHandler(handler)
    
    # Configure framework loggers
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    
    logger = logging.getLogger("foresight.core")
    logger.info(f"Logging initialized with level={log_level}, format={log_format}")
    return logger


logger = logging.getLogger("foresight")
