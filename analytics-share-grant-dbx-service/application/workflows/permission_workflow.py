import logging
import uuid
from datetime import datetime, timezone
from typing import List

from application.dto.operation_result_dto import (
    AppliedResultDTO,
    OperationErrorDTO,
    OperationResultDTO,
)
from application.dto.permission_request_dto import PermissionRequestDTO
from application.ports.outbound.controller_port import ControllerPort
from application.services.operation_planner import OperationPlanner
from application.use_cases.grant_permission import GrantPermissionUseCase
from application.use_cases.revoke_permission import RevokePermissionUseCase
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.operation_type import OperationType
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType
from domain.exceptions.domain_exceptions import DomainException

logger = logging.getLogger(__name__)


class PermissionWorkflow:
    def __init__(
        self,
        planner: OperationPlanner,
        grant_use_case: GrantPermissionUseCase,
        revoke_use_case: RevokePermissionUseCase,
        controller_port: ControllerPort,
    ):
        self.planner = planner
        self.grant_use_case = grant_use_case
        self.revoke_use_case = revoke_use_case
        self.controller_port = controller_port

    def execute(self, request: PermissionRequestDTO) -> OperationResultDTO:
        started_at = datetime.now(timezone.utc).isoformat()
        event_id = f"evt-{uuid.uuid4()}"

        logger.info(
            f"Starting workflow for request {request.request_id} (Operation: {request.operation})"
        )

        try:
            # 1. Parse and build domain entities
            operation = OperationType(request.operation.upper())
            principal = Principal(type=request.principal.type, name=request.principal.name)
            resource = Resource(
                type=ResourceType(request.resource.type.upper()),
                catalog=request.resource.catalog,
                schema=request.resource.schema,
                name=request.resource.name,
            )
            requested_privileges = [
                Privilege(p.upper()) for p in request.requested_privileges
            ]

            # 2. Plan operation (validates principal & resource, analyzes diff)
            plan = self.planner.create_plan(
                operation=operation,
                resource=resource,
                principal=principal,
                requested_privileges=requested_privileges,
            )

            applied_privileges: List[str] = []

            # 3. Apply changes with idempotency
            if plan.is_noop:
                logger.info(
                    f"Idempotent execution: no changes needed for request {request.request_id}"
                )
                if operation == OperationType.GRANT:
                    applied_privileges = [p.value for p in requested_privileges]
                else:
                    applied_privileges = []
            else:
                if operation == OperationType.GRANT:
                    granted = self.grant_use_case.execute(
                        resource=resource,
                        principal=principal,
                        privileges_to_grant=plan.privileges_to_apply,
                    )
                    applied_privileges = [p.value for p in granted]
                else:
                    revoked = self.revoke_use_case.execute(
                        resource=resource,
                        principal=principal,
                        privileges_to_revoke=plan.privileges_to_apply,
                    )
                    applied_privileges = [p.value for p in revoked]

            finished_at = datetime.now(timezone.utc).isoformat()

            result_dto = OperationResultDTO(
                event_id=event_id,
                request_id=request.request_id,
                status="SUCCEEDED",
                started_at=started_at,
                finished_at=finished_at,
                result=AppliedResultDTO(
                    operation=operation.value,
                    resource=resource.full_name,
                    principal=principal.name,
                    applied_privileges=applied_privileges,
                ),
            )

        except DomainException as e:
            logger.warning(
                f"Domain exception during workflow for {request.request_id}: {e.code} - {e.message}"
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            result_dto = OperationResultDTO(
                event_id=event_id,
                request_id=request.request_id,
                status="FAILED",
                started_at=started_at,
                finished_at=finished_at,
                error=OperationErrorDTO(
                    code=e.code,
                    message=e.message,
                ),
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during workflow for {request.request_id}: {e}",
                exc_info=True,
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            result_dto = OperationResultDTO(
                event_id=event_id,
                request_id=request.request_id,
                status="FAILED",
                started_at=started_at,
                finished_at=finished_at,
                error=OperationErrorDTO(
                    code="INTERNAL_PROCESSING_ERROR",
                    message=str(e),
                ),
            )

        # 4. Deliver result to Controller via outbound Port
        try:
            self.controller_port.send_callback(result_dto)
        except Exception as e:
            logger.error(
                f"Failed to send callback to Controller for {request.request_id}: {e}"
            )

        return result_dto
