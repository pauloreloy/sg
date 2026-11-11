import pytest
from domain.entities.outbox import OutboxItemEntity
from domain.entities.request import PrincipalEntity, ResourceEntity, ShareGrantRequestEntity
from domain.enums import DispatchStatus, ExecutionStatus, NotificationStatus, OperationType
from domain.exceptions import ControllerDomainException, RequestNotFoundException


def test_request_entity_creation():
    principal = PrincipalEntity(type="GROUP", name="analytics_readers")
    resource = ResourceEntity(type="TABLE", catalog="shared", schema="sales", name="orders")

    assert resource.full_name == "shared.sales.orders"

    entity = ShareGrantRequestEntity(
        request_id="req-123",
        operation=OperationType.GRANT,
        workspace_id="ws-1",
        principal=principal,
        resource=resource,
        requested_privileges=["SELECT"],
        dispatch_status=DispatchStatus.PENDING,
        execution_status=ExecutionStatus.NOT_STARTED,
    )

    assert entity.request_id == "req-123"
    assert entity.operation == OperationType.GRANT
    assert entity.dispatch_status == DispatchStatus.PENDING
    assert entity.execution_status == ExecutionStatus.NOT_STARTED


def test_outbox_item_entity():
    outbox = OutboxItemEntity(
        event_id="evt-123",
        request_id="req-123",
        event_type="SHARE_GRANT_COMPLETED",
        status=NotificationStatus.PENDING,
        created_at="2026-11-10T20:00:00Z",
        payload={"execution_status": "SUCCEEDED"},
    )
    assert outbox.event_id == "evt-123"
    assert outbox.status == NotificationStatus.PENDING
