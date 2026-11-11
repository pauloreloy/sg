from unittest.mock import MagicMock
import pytest
from application.dto.callback_dto import CallbackRequestDTO, CallbackResultDTO
from application.dto.submission_dto import (
    PrincipalInputDTO,
    ResourceInputDTO,
    SubmissionMetadataDTO,
    SubmissionRequestDTO,
)
from application.ports.outbound.event_publisher_port import EventPublisherPort
from application.ports.outbound.message_dispatcher_port import MessageDispatcherPort
from application.ports.outbound.outbox_repository_port import OutboxRepositoryPort
from application.ports.outbound.request_repository_port import RequestRepositoryPort
from application.use_cases.get_request_status_use_case import GetRequestStatusUseCase
from application.use_cases.process_callback_use_case import ProcessCallbackUseCase
from application.use_cases.publish_outbox_use_case import PublishOutboxUseCase
from application.use_cases.reconcile_dispatches_use_case import ReconcileDispatchesUseCase
from application.use_cases.submit_request_use_case import SubmitRequestUseCase
from domain.entities.outbox import OutboxItemEntity
from domain.entities.request import (
    PrincipalEntity,
    ResourceEntity,
    ShareGrantRequestEntity,
)
from domain.enums import DispatchStatus, ExecutionStatus, NotificationStatus, OperationType
from domain.exceptions import RequestNotFoundException


def test_submit_request_use_case_success():
    req_repo = MagicMock(spec=RequestRepositoryPort)
    dispatcher = MagicMock(spec=MessageDispatcherPort)
    req_repo.get_by_idempotency_key.return_value = None

    use_case = SubmitRequestUseCase(request_repository=req_repo, message_dispatcher=dispatcher)

    dto = SubmissionRequestDTO(
        operation="GRANT",
        workspace_id="ws-dev",
        principal=PrincipalInputDTO(type="GROUP", name="analytics_readers"),
        resource=ResourceInputDTO(type="TABLE", catalog="shared", schema="sales", name="orders"),
        requested_privileges=["SELECT"],
        metadata=SubmissionMetadataDTO(correlation_id="corr-1", idempotency_key="key-1"),
    )

    response = use_case.submit(dto)

    assert response.status == "ACCEPTED"
    assert response.dispatch_status == "DISPATCHED"
    assert response.request_id.startswith("req-")

    req_repo.save_initial.assert_called_once()
    dispatcher.dispatch.assert_called_once()
    req_repo.update_dispatch.assert_called_once_with(
        request_id=response.request_id,
        new_status=DispatchStatus.DISPATCHED,
        expected_status=DispatchStatus.PENDING,
    )


def test_submit_request_idempotency():
    req_repo = MagicMock(spec=RequestRepositoryPort)
    dispatcher = MagicMock(spec=MessageDispatcherPort)

    existing = ShareGrantRequestEntity(
        request_id="req-existing",
        operation=OperationType.GRANT,
        workspace_id="ws-dev",
        principal=PrincipalEntity("GROUP", "readers"),
        resource=ResourceEntity("TABLE", "shared", "sales", "orders"),
        requested_privileges=["SELECT"],
        dispatch_status=DispatchStatus.DISPATCHED,
        execution_status=ExecutionStatus.SUCCEEDED,
    )
    req_repo.get_by_idempotency_key.return_value = existing

    use_case = SubmitRequestUseCase(request_repository=req_repo, message_dispatcher=dispatcher)

    dto = SubmissionRequestDTO(
        operation="GRANT",
        workspace_id="ws-dev",
        principal=PrincipalInputDTO("GROUP", "readers"),
        resource=ResourceInputDTO("TABLE", "shared", "sales", "orders"),
        requested_privileges=["SELECT"],
        metadata=SubmissionMetadataDTO(idempotency_key="key-existing"),
    )

    response = use_case.submit(dto)

    assert response.request_id == "req-existing"
    assert response.dispatch_status == "DISPATCHED"
    dispatcher.dispatch.assert_not_called()


def test_process_callback_success():
    req_repo = MagicMock(spec=RequestRepositoryPort)
    outbox_repo = MagicMock(spec=OutboxRepositoryPort)

    existing = ShareGrantRequestEntity(
        request_id="req-123",
        operation=OperationType.GRANT,
        workspace_id="ws-dev",
        principal=PrincipalEntity("GROUP", "readers"),
        resource=ResourceEntity("TABLE", "shared", "sales", "orders"),
        requested_privileges=["SELECT"],
    )
    req_repo.get_by_id.return_value = existing

    use_case = ProcessCallbackUseCase(
        request_repository=req_repo,
        outbox_repository=outbox_repo,
    )

    callback_dto = CallbackRequestDTO(
        request_id="req-123",
        event_id="evt-456",
        status="SUCCEEDED",
        started_at="2026-11-10T20:00:00Z",
        finished_at="2026-11-10T20:00:10Z",
        result=CallbackResultDTO(
            operation="GRANT",
            resource="shared.sales.orders",
            principal="readers",
            applied_privileges=["SELECT"],
        ),
    )

    resp = use_case.process(callback_dto)
    assert resp.request_id == "req-123"
    assert resp.callback_status == "ACCEPTED"

    outbox_repo.save_callback_and_outbox.assert_called_once()


def test_process_callback_not_found():
    req_repo = MagicMock(spec=RequestRepositoryPort)
    outbox_repo = MagicMock(spec=OutboxRepositoryPort)
    req_repo.get_by_id.return_value = None

    use_case = ProcessCallbackUseCase(request_repository=req_repo, outbox_repository=outbox_repo)

    callback_dto = CallbackRequestDTO(
        request_id="req-missing",
        event_id="evt-456",
        status="SUCCEEDED",
        started_at="2026-11-10T20:00:00Z",
        finished_at="2026-11-10T20:00:10Z",
    )

    with pytest.raises(RequestNotFoundException):
        use_case.process(callback_dto)


def test_publish_outbox():
    outbox_repo = MagicMock(spec=OutboxRepositoryPort)
    event_pub = MagicMock(spec=EventPublisherPort)

    items = [
        OutboxItemEntity(
            event_id="evt-1",
            request_id="req-1",
            event_type="SHARE_GRANT_COMPLETED",
            status=NotificationStatus.PENDING,
            created_at="2026-11-10T20:00:00Z",
            payload={"execution_status": "SUCCEEDED"},
        )
    ]
    outbox_repo.get_pending_items.return_value = items

    use_case = PublishOutboxUseCase(outbox_repository=outbox_repo, event_publisher=event_pub)
    count = use_case.publish_pending()

    assert count == 1
    event_pub.publish.assert_called_once()
    outbox_repo.mark_published.assert_called_once_with(event_id="evt-1", request_id="req-1")


def test_reconcile_dispatches():
    req_repo = MagicMock(spec=RequestRepositoryPort)
    dispatcher = MagicMock(spec=MessageDispatcherPort)

    stuck_req = ShareGrantRequestEntity(
        request_id="req-stuck",
        operation=OperationType.GRANT,
        workspace_id="ws-dev",
        principal=PrincipalEntity("GROUP", "readers"),
        resource=ResourceEntity("TABLE", "shared", "sales", "orders"),
        requested_privileges=["SELECT"],
        dispatch_status=DispatchStatus.PENDING,
        dispatch_attempts=0,
    )
    req_repo.get_stuck_pending.return_value = [stuck_req]

    use_case = ReconcileDispatchesUseCase(
        request_repository=req_repo, message_dispatcher=dispatcher
    )
    count = use_case.reconcile()

    assert count == 1
    dispatcher.dispatch.assert_called_once()
    req_repo.update_dispatch.assert_called_once_with(
        request_id="req-stuck",
        new_status=DispatchStatus.DISPATCHED,
        expected_status=DispatchStatus.PENDING,
    )
