import logging
import uuid
from datetime import datetime, timezone
from application.dto.submission_dto import (
    SubmissionRequestDTO,
    SubmissionResponseDTO,
)
from application.ports.inbound.submit_request_port import SubmitRequestPort
from application.ports.outbound.message_dispatcher_port import MessageDispatcherPort
from application.ports.outbound.request_repository_port import RequestRepositoryPort
from domain.entities.request import (
    PrincipalEntity,
    ResourceEntity,
    ShareGrantRequestEntity,
)
from domain.enums import DispatchStatus, ExecutionStatus, OperationType

logger = logging.getLogger(__name__)


class SubmitRequestUseCase(SubmitRequestPort):
    def __init__(
        self,
        request_repository: RequestRepositoryPort,
        message_dispatcher: MessageDispatcherPort,
    ):
        self.request_repository = request_repository
        self.message_dispatcher = message_dispatcher

    def submit(self, request: SubmissionRequestDTO) -> SubmissionResponseDTO:
        idempotency_key = (
            request.metadata.idempotency_key if request.metadata else None
        )
        correlation_id = (
            request.metadata.correlation_id
            if request.metadata and request.metadata.correlation_id
            else str(uuid.uuid4())
        )

        # 1. Check idempotency
        if idempotency_key:
            existing = self.request_repository.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(
                    f"Idempotent match: request {existing.request_id} already exists for key {idempotency_key}"
                )
                return SubmissionResponseDTO(
                    request_id=existing.request_id,
                    status="ACCEPTED",
                    dispatch_status=existing.dispatch_status.value,
                )

        # 2. Generate unique request_id
        request_id = f"req-{uuid.uuid4()}"
        now = datetime.now(timezone.utc).isoformat()

        operation_enum = OperationType(request.operation.upper())

        entity = ShareGrantRequestEntity(
            request_id=request_id,
            operation=operation_enum,
            target="DATABRICKS",
            workspace_id=request.workspace_id,
            principal=PrincipalEntity(
                type=request.principal.type,
                name=request.principal.name,
            ),
            resource=ResourceEntity(
                type=request.resource.type,
                catalog=request.resource.catalog,
                schema=request.resource.schema,
                name=request.resource.name,
            ),
            requested_privileges=request.requested_privileges,
            dispatch_status=DispatchStatus.PENDING,
            execution_status=ExecutionStatus.NOT_STARTED,
            created_at=now,
            updated_at=now,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            dispatch_attempts=0,
        )

        # 3. Persist PENDING state in DynamoDB
        self.request_repository.save_initial(entity)

        # 4. Publish message to SQS
        sqs_message = {
            "message_version": "1",
            "request_id": request_id,
            "operation": operation_enum.value,
            "workspace_id": request.workspace_id,
            "principal": {
                "type": request.principal.type,
                "name": request.principal.name,
            },
            "resource": {
                "type": request.resource.type,
                "catalog": request.resource.catalog,
                "schema": request.resource.schema,
                "name": request.resource.name,
            },
            "requested_privileges": request.requested_privileges,
            "correlation_id": correlation_id,
        }

        try:
            self.message_dispatcher.dispatch(sqs_message)
        except Exception as e:
            logger.error(f"Failed to dispatch request {request_id} to SQS: {e}")
            raise

        # 5. Update state to DISPATCHED
        try:
            self.request_repository.update_dispatch(
                request_id=request_id,
                new_status=DispatchStatus.DISPATCHED,
                expected_status=DispatchStatus.PENDING,
            )
        except Exception as e:
            logger.warning(
                f"Dispatched to SQS but state update to DISPATCHED failed for {request_id}: {e}"
            )

        return SubmissionResponseDTO(
            request_id=request_id,
            status="ACCEPTED",
            dispatch_status=DispatchStatus.DISPATCHED.value,
        )
