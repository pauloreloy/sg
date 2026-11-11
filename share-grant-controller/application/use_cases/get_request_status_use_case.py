from typing import Optional
from application.dto.request_status_dto import RequestStatusDTO
from application.ports.inbound.get_request_status_port import GetRequestStatusPort
from application.ports.outbound.request_repository_port import RequestRepositoryPort


class GetRequestStatusUseCase(GetRequestStatusPort):
    def __init__(self, request_repository: RequestRepositoryPort):
        self.request_repository = request_repository

    def get_status(self, request_id: str) -> Optional[RequestStatusDTO]:
        req = self.request_repository.get_by_id(request_id)
        if not req:
            return None

        return RequestStatusDTO(
            request_id=req.request_id,
            operation=req.operation.value,
            target=req.target,
            workspace_id=req.workspace_id,
            principal={"type": req.principal.type, "name": req.principal.name},
            resource={
                "type": req.resource.type,
                "catalog": req.resource.catalog,
                "schema": req.resource.schema,
                "name": req.resource.name,
            },
            requested_privileges=req.requested_privileges,
            dispatch_status=req.dispatch_status.value,
            execution_status=req.execution_status.value,
            notification_status=req.notification_status.value if req.notification_status else None,
            created_at=req.created_at,
            updated_at=req.updated_at,
            correlation_id=req.correlation_id,
            idempotency_key=req.idempotency_key,
            result=req.result,
            error=req.error,
        )
