import logging
from typing import Callable, Optional
from fastapi import APIRouter, HTTPException, status

from adapters.inbound.http.schemas import (
    CallbackHttpPayload,
    CallbackHttpResponse,
    RequestStatusHttpResponse,
    SubmissionHttpPayload,
    SubmissionHttpResponse,
)
from application.dto.callback_dto import (
    CallbackErrorDTO,
    CallbackRequestDTO,
    CallbackResultDTO,
)
from application.dto.submission_dto import (
    PrincipalInputDTO,
    ResourceInputDTO,
    SubmissionMetadataDTO,
    SubmissionRequestDTO,
)
from application.ports.inbound.get_request_status_port import GetRequestStatusPort
from application.ports.inbound.process_callback_port import ProcessCallbackPort
from application.ports.inbound.submit_request_port import SubmitRequestPort
from domain.exceptions import ControllerDomainException, RequestNotFoundException

logger = logging.getLogger(__name__)


def create_router(
    submit_use_case: SubmitRequestPort,
    callback_use_case: ProcessCallbackPort,
    get_status_use_case: GetRequestStatusPort,
    health_checker: Optional[Callable[[], dict]] = None,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/share-grant",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=SubmissionHttpResponse,
        summary="Submit a Grant or Revoke permission request",
    )
    def submit_share_grant(payload: SubmissionHttpPayload) -> SubmissionHttpResponse:
        """
        Receives request from API Gateway (already authenticated by API Gateway),
        persists PENDING state in DynamoDB, dispatches to SQS, updates to DISPATCHED,
        and returns 202 Accepted immediately.
        """
        meta_dto = None
        if payload.metadata:
            meta_dto = SubmissionMetadataDTO(
                requested_by=payload.metadata.requested_by,
                correlation_id=payload.metadata.correlation_id,
                idempotency_key=payload.metadata.idempotency_key,
            )

        dto = SubmissionRequestDTO(
            operation=payload.operation,
            workspace_id=payload.workspace_id,
            principal=PrincipalInputDTO(
                type=payload.principal.type,
                name=payload.principal.name,
            ),
            resource=ResourceInputDTO(
                type=payload.resource.type,
                catalog=payload.resource.catalog,
                schema=payload.resource.schema_name,
                name=payload.resource.name,
            ),
            requested_privileges=payload.requested_privileges,
            metadata=meta_dto,
        )

        try:
            response_dto = submit_use_case.submit(dto)
            return SubmissionHttpResponse(
                request_id=response_dto.request_id,
                status=response_dto.status,
                dispatch_status=response_dto.dispatch_status,
            )
        except ControllerDomainException as e:
            logger.error(f"Domain error during submission: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": e.code, "message": e.message},
            )
        except Exception as e:
            logger.error(f"Unexpected error during submission: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "INTERNAL_SERVER_ERROR", "message": str(e)},
            )

    @router.post(
        "/share-grant/{request_id}/result",
        status_code=status.HTTP_200_OK,
        response_model=CallbackHttpResponse,
        summary="Callback endpoint for Databricks service to deliver execution result",
    )
    def handle_callback(
        request_id: str,
        payload: CallbackHttpPayload,
    ) -> CallbackHttpResponse:
        """
        Receives execution result from Databricks service via HTTP callback.
        No token validation here as entry authentication is handled by the API Gateway.
        Atomically updates request state and writes Outbox record.
        """
        res_dto = None
        if payload.result:
            res_dto = CallbackResultDTO(
                operation=payload.result.operation,
                resource=payload.result.resource,
                principal=payload.result.principal,
                applied_privileges=payload.result.applied_privileges,
            )

        err_dto = None
        if payload.error:
            err_dto = CallbackErrorDTO(
                code=payload.error.code,
                message=payload.error.message,
            )

        dto = CallbackRequestDTO(
            request_id=request_id,
            event_id=payload.event_id,
            status=payload.status,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            result=res_dto,
            error=err_dto,
        )

        try:
            response_dto = callback_use_case.process(dto)
            return CallbackHttpResponse(
                request_id=response_dto.request_id,
                callback_status=response_dto.callback_status,
            )
        except RequestNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": e.code, "message": e.message},
            )
        except ControllerDomainException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": e.code, "message": e.message},
            )
        except Exception as e:
            logger.error(f"Unexpected error in callback handling: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "INTERNAL_SERVER_ERROR", "message": str(e)},
            )

    @router.get(
        "/share-grant/{request_id}",
        response_model=RequestStatusHttpResponse,
        summary="Get request status and execution details",
    )
    def get_status(request_id: str) -> RequestStatusHttpResponse:
        req = get_status_use_case.get_status(request_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "REQUEST_NOT_FOUND",
                    "message": f"Request {request_id} not found.",
                },
            )

        return RequestStatusHttpResponse(
            request_id=req.request_id,
            operation=req.operation,
            target=req.target,
            workspace_id=req.workspace_id,
            principal=req.principal,
            resource=req.resource,
            requested_privileges=req.requested_privileges,
            dispatch_status=req.dispatch_status,
            execution_status=req.execution_status,
            notification_status=req.notification_status,
            created_at=req.created_at,
            updated_at=req.updated_at,
            correlation_id=req.correlation_id,
            idempotency_key=req.idempotency_key,
            result=req.result,
            error=req.error,
        )

    @router.get("/health", summary="Health check endpoint")
    def health() -> dict:
        if health_checker:
            return health_checker()
        return {"status": "UP", "service": "share-grant-controller"}

    return router
