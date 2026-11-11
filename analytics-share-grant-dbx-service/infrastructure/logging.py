import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter matching section 2 of doc 06."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "analytics-share-grant-dbx-service",
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Include structured context attributes if present
        for field in [
            "request_id",
            "correlation_id",
            "event_id",
            "operation",
            "workspace_id",
            "resource_type",
            "step",
            "attempt",
            "duration_ms",
            "error_code",
        ]:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers = [handler]
