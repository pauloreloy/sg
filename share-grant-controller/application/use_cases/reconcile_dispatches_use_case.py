import logging
from application.ports.inbound.reconcile_dispatches_port import ReconcileDispatchesPort
from application.ports.outbound.message_dispatcher_port import MessageDispatcherPort
from application.ports.outbound.request_repository_port import RequestRepositoryPort
from domain.enums import DispatchStatus

logger = logging.getLogger(__name__)


class ReconcileDispatchesUseCase(ReconcileDispatchesPort):
    def __init__(
        self,
        request_repository: RequestRepositoryPort,
        message_dispatcher: MessageDispatcherPort,
        threshold_seconds: int = 60,
        max_attempts: int = 3,
    ):
        self.request_repository = request_repository
        self.message_dispatcher = message_dispatcher
        self.threshold_seconds = threshold_seconds
        self.max_attempts = max_attempts

    def reconcile(self) -> int:
        stuck_requests = self.request_repository.get_stuck_pending(
            threshold_seconds=self.threshold_seconds
        )
        reconciled = 0

        for req in stuck_requests:
            logger.warning(
                f"Reconciling stuck request {req.request_id} (attempts: {req.dispatch_attempts})"
            )

            if req.dispatch_attempts >= self.max_attempts:
                logger.error(
                    f"Request {req.request_id} exceeded max attempts ({self.max_attempts}). Marking DISPATCH_FAILED."
                )
                self.request_repository.update_dispatch(
                    request_id=req.request_id,
                    new_status=DispatchStatus.DISPATCH_FAILED,
                )
                continue

            sqs_message = {
                "message_version": "1",
                "request_id": req.request_id,
                "operation": req.operation.value,
                "workspace_id": req.workspace_id,
                "principal": {
                    "type": req.principal.type,
                    "name": req.principal.name,
                },
                "resource": {
                    "type": req.resource.type,
                    "catalog": req.resource.catalog,
                    "schema": req.resource.schema,
                    "name": req.resource.name,
                },
                "requested_privileges": req.requested_privileges,
                "correlation_id": req.correlation_id,
            }

            try:
                self.message_dispatcher.dispatch(sqs_message)
                self.request_repository.update_dispatch(
                    request_id=req.request_id,
                    new_status=DispatchStatus.DISPATCHED,
                    expected_status=DispatchStatus.PENDING,
                )
                reconciled += 1
                logger.info(f"Reconciled {req.request_id} to DISPATCHED")
            except Exception as e:
                logger.error(f"Reconciliation dispatch error for {req.request_id}: {e}")

        return reconciled
