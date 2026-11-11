from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from adapters.inbound.http.router import create_router
from application.dto.callback_dto import CallbackResponseDTO
from application.dto.request_status_dto import RequestStatusDTO
from application.dto.submission_dto import SubmissionResponseDTO
from application.ports.inbound.get_request_status_port import GetRequestStatusPort
from application.ports.inbound.process_callback_port import ProcessCallbackPort
from application.ports.inbound.submit_request_port import SubmitRequestPort
from domain.exceptions import RequestNotFoundException


@pytest.fixture
def test_app():
    submit_port = MagicMock(spec=SubmitRequestPort)
    callback_port = MagicMock(spec=ProcessCallbackPort)
    status_port = MagicMock(spec=GetRequestStatusPort)

    router = create_router(
        submit_use_case=submit_port,
        callback_use_case=callback_port,
        get_status_use_case=status_port,
    )

    app = FastAPI()
    app.include_router(router)
    return app, submit_port, callback_port, status_port


def test_post_share_grant_accepted(test_app):
    app, submit_port, _, _ = test_app
    client = TestClient(app)

    submit_port.submit.return_value = SubmissionResponseDTO(
        request_id="req-test-1",
        status="ACCEPTED",
        dispatch_status="DISPATCHED",
    )

    payload = {
        "operation": "GRANT",
        "workspace_id": "workspace-identifier",
        "principal": {"type": "GROUP", "name": "analytics_readers"},
        "resource": {"type": "TABLE", "catalog": "shared", "schema": "sales", "name": "orders"},
        "requested_privileges": ["SELECT"],
        "metadata": {"requested_by": "system-a", "correlation_id": "corr-123"},
    }

    response = client.post("/share-grant", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["request_id"] == "req-test-1"
    assert data["status"] == "ACCEPTED"
    assert data["dispatch_status"] == "DISPATCHED"


def test_post_callback_success_without_token(test_app):
    """Verifies that API Gateway handles authentication and controller does not require token."""
    app, _, callback_port, _ = test_app
    client = TestClient(app)

    callback_port.process.return_value = CallbackResponseDTO(
        request_id="req-test-1",
        callback_status="ACCEPTED",
    )

    payload = {
        "event_id": "evt-test-1",
        "status": "SUCCEEDED",
        "started_at": "2026-11-10T20:00:00Z",
        "finished_at": "2026-11-10T20:00:42Z",
        "result": {
            "operation": "GRANT",
            "resource": "shared.sales.orders",
            "principal": "analytics_readers",
            "applied_privileges": ["SELECT"],
        },
    }

    # No token provided
    response = client.post("/share-grant/req-test-1/result", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-test-1"
    assert data["callback_status"] == "ACCEPTED"


def test_post_callback_not_found(test_app):
    app, _, callback_port, _ = test_app
    client = TestClient(app)

    callback_port.process.side_effect = RequestNotFoundException("req-nonexistent")

    payload = {
        "event_id": "evt-1",
        "status": "FAILED",
        "started_at": "2026-11-10T20:00:00Z",
        "finished_at": "2026-11-10T20:00:10Z",
        "error": {"code": "RESOURCE_NOT_FOUND", "message": "Not found"},
    }

    response = client.post("/share-grant/req-nonexistent/result", json=payload)
    assert response.status_code == 404


def test_get_request_status(test_app):
    app, _, _, status_port = test_app
    client = TestClient(app)

    status_port.get_status.return_value = RequestStatusDTO(
        request_id="req-test-1",
        operation="GRANT",
        target="DATABRICKS",
        workspace_id="ws-1",
        principal={"type": "GROUP", "name": "readers"},
        resource={"type": "TABLE", "catalog": "c", "schema": "s", "name": "t"},
        requested_privileges=["SELECT"],
        dispatch_status="DISPATCHED",
        execution_status="SUCCEEDED",
        notification_status="PUBLISHED",
        created_at="2026-11-10T20:00:00Z",
        updated_at="2026-11-10T20:00:42Z",
        correlation_id="corr-1",
        idempotency_key="key-1",
    )

    response = client.get("/share-grant/req-test-1")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-test-1"
    assert data["execution_status"] == "SUCCEEDED"


def test_get_request_status_not_found(test_app):
    app, _, _, status_port = test_app
    client = TestClient(app)

    status_port.get_status.return_value = None

    response = client.get("/share-grant/req-missing")
    assert response.status_code == 404
