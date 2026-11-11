import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def measure_duration(step_name: str, extra: dict = None):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_data = {"step": step_name, "duration_ms": round(duration_ms, 2)}
        if extra:
            log_data.update(extra)
        logger.info(f"Step '{step_name}' completed in {duration_ms:.2f}ms", extra=log_data)
