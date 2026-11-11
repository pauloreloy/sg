import logging
import time
from typing import Any, Dict
import httpx

from application.dto.operation_result_dto import OperationResultDTO
from application.ports.outbound.controller_port import ControllerPort
from infrastructure.config import Settings, settings

logger = logging.getLogger(__name__)


class ControllerHttpAdapter(ControllerPort):
    def __init__(self, config: Settings = settings):
        self.config = config
        self.base_url = config.controller_url.rstrip("/")
        self.max_retries = config.callback_max_retries
        self.backoff_factor = config.callback_retry_backoff_seconds

    def send_callback(self, result: OperationResultDTO) -> bool:
        url = f"{self.base_url}/share-grant/{result.request_id}/result"

        payload: Dict[str, Any] = {
            "event_id": result.event_id,
            "status": result.status,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
        }

        if result.result:
            payload["result"] = {
                "operation": result.result.operation,
                "resource": result.result.resource,
                "principal": result.result.principal,
                "applied_privileges": result.result.applied_privileges,
            }

        if result.error:
            payload["error"] = {
                "code": result.error.code,
                "message": result.error.message,
            }

        headers = {
            "Content-Type": "application/json",
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Sending callback to Controller for {result.request_id} (Attempt {attempt}/{self.max_retries}) -> {url}"
                )
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(url, json=payload, headers=headers)

                if response.status_code in (200, 202):
                    logger.info(
                        f"Callback accepted by Controller for request {result.request_id} (HTTP {response.status_code})"
                    )
                    return True
                else:
                    logger.warning(
                        f"Controller returned HTTP {response.status_code}: {response.text}"
                    )

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed sending callback to Controller: {e}"
                )

            if attempt < self.max_retries:
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_time)

        logger.error(
            f"Failed to deliver callback to Controller for request {result.request_id} after {self.max_retries} attempts"
        )
        return False
