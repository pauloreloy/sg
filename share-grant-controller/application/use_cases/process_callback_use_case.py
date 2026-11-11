import logging
from datetime import datetime, timezone
from application.dto.callback_dto import CallbackRequestDTO, CallbackResponseDTO
from application.ports.inbound.process_callback_port import ProcessCallbackPort
from application.ports.outbound.outbox_repository_port import OutboxRepositoryPort
from application.ports.outbound.request_repository_port import RequestRepositoryPort
from domain.entities.outbox import OutboxItemEntity
from domain.enums import ExecutionStatus, NotificationStatus
from domain.exceptions import RequestNotFoundException

logger = logging.getLogger(__name__)


class ProcessCallbackUseCase(ProcessCallbackPort):
    def __init__(
        self,
        request_repository: RequestRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
    ):
        self.request_repository = request_repository
        self.outbox_repository = outbox_repository

    def process(self, callback: CallbackRequestDTO) -> CallbackResponseDTO:
        # Check if request exists
        existing = self.request_repository.get_by_id(callback.request_id)
        if not existing:
            logger.warning(f"Callback received for non-existent request: {callback.request_id}")
            raise RequestNotFoundException(callback.request_id)

        now = datetime.now(timezone.utc).isoformat()
        status_enum = ExecutionStatus(callback.status.upper())

        # Construct Outbox item payload
        outbox_payload = {
            "execution_status": status_enum.value,
            "started_at": callback.started_at,
            "finished_at": callback.finished_at,
        }

        result_dict = None
        if callback.result:
            result_dict = {
                "operation": callback.result.operation,
                "resource": callback.result.resource,
                "principal": callback.result.principal,
                "applied_privileges": callback.result.applied_privileges,
            }
            outbox_payload["result"] = result_dict

        error_dict = None
        if callback.error:
            error_dict = {
                "code": callback.error.code,
                "message": callback.error.message,
            }
            outbox_payload["error"] = error_dict

        outbox_item = OutboxItemEntity(
            event_id=callback.event_id,
            request_id=callback.request_id,
            event_type="SHARE_GRANT_COMPLETED",
            status=NotificationStatus.PENDING,
            created_at=now,
            updated_at=now,
            payload=outbox_payload,
        )

        # Atomic transaction to save callback result and outbox entry
        self.outbox_repository.save_callback_and_outbox(
            request_id=callback.request_id,
            outbox_item=outbox_item,
            status=status_enum,
            result=result_dict,
            error=error_dict,
        )

        logger.info(
            f"Successfully processed callback for request {callback.request_id} with status {status_enum.value}"
        )

        return CallbackResponseDTO(
            request_id=callback.request_id,
            callback_status="ACCEPTED",
        )
