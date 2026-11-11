import json
import os
import subprocess
import sys
from fastapi.testclient import TestClient
import pytest


def test_end_to_end_integration():
    """
    End-to-End integration test:
    1. Submits Grant request to Controller via HTTP (TestClient).
    2. Runs Databricks workflow in an isolated process to simulate SQS consumer processing.
    3. Databricks workflow executes Grant in Unity Catalog and sends callback to Controller.
    4. Controller updates request state to SUCCEEDED and creates Outbox entry.
    5. Outbox publisher publishes event to SNS.
    6. Verifies request status is SUCCEEDED and notification_status is PUBLISHED.
    """
    controller_dir = os.path.abspath("share-grant-controller")
    dbx_dir = os.path.abspath("analytics-share-grant-dbx-service")

    py_exec = sys.executable

    script = """
import sys
import json
import subprocess
from fastapi import FastAPI
from fastapi.testclient import TestClient

controller_dir = sys.argv[1]
dbx_dir = sys.argv[2]
py_exec = sys.argv[3]

sys.path.insert(0, controller_dir)

from application.ports.outbound.request_repository_port import RequestRepositoryPort
from application.ports.outbound.outbox_repository_port import OutboxRepositoryPort
from application.ports.outbound.message_dispatcher_port import MessageDispatcherPort
from application.ports.outbound.event_publisher_port import EventPublisherPort
from application.use_cases.submit_request_use_case import SubmitRequestUseCase
from application.use_cases.process_callback_use_case import ProcessCallbackUseCase
from application.use_cases.get_request_status_use_case import GetRequestStatusUseCase
from application.use_cases.publish_outbox_use_case import PublishOutboxUseCase
from adapters.inbound.http.router import create_router
from domain.enums import DispatchStatus, ExecutionStatus, NotificationStatus

requests_db = {}
outbox_db = {}
sqs_messages = []
sns_events = []

class InMemoryReqRepo(RequestRepositoryPort):
    def save_initial(self, request):
        requests_db[request.request_id] = request
    def update_dispatch(self, request_id, new_status, expected_status=None):
        requests_db[request_id].dispatch_status = new_status
    def get_by_id(self, request_id):
        return requests_db.get(request_id)
    def get_by_idempotency_key(self, key):
        for r in requests_db.values():
            if r.idempotency_key == key:
                return r
        return None
    def get_stuck_pending(self, threshold):
        return []

class InMemoryOutboxRepo(OutboxRepositoryPort):
    def save_callback_and_outbox(self, request_id, outbox_item, status, result=None, error=None):
        req = requests_db[request_id]
        req.execution_status = status
        req.notification_status = NotificationStatus.PENDING
        req.result = result
        req.error = error
        outbox_db[outbox_item.event_id] = outbox_item
    def get_pending_items(self, limit=50):
        return [i for i in outbox_db.values() if i.status == NotificationStatus.PENDING]
    def mark_published(self, event_id, request_id):
        outbox_db[event_id].status = NotificationStatus.PUBLISHED
        requests_db[request_id].notification_status = NotificationStatus.PUBLISHED

class InMemoryDispatcher(MessageDispatcherPort):
    def dispatch(self, message):
        sqs_messages.append(message)
        return "msg-123"

class InMemoryPublisher(EventPublisherPort):
    def publish(self, event_payload, attributes=None):
        sns_events.append(event_payload)
        return "sns-123"

req_repo = InMemoryReqRepo()
outbox_repo = InMemoryOutboxRepo()
dispatcher = InMemoryDispatcher()
publisher = InMemoryPublisher()

submit_uc = SubmitRequestUseCase(req_repo, dispatcher)
callback_uc = ProcessCallbackUseCase(req_repo, outbox_repo)
status_uc = GetRequestStatusUseCase(req_repo)
publish_outbox_uc = PublishOutboxUseCase(outbox_repo, publisher)

app = FastAPI()
app.include_router(create_router(submit_uc, callback_uc, status_uc))
client = TestClient(app)

# 1. Submit Request via HTTP
submission_payload = {
    "operation": "GRANT",
    "workspace_id": "ws-1",
    "principal": {"type": "GROUP", "name": "analytics_readers"},
    "resource": {"type": "TABLE", "catalog": "shared", "schema": "sales", "name": "orders"},
    "requested_privileges": ["SELECT"],
    "metadata": {"correlation_id": "corr-101", "idempotency_key": "key-101"}
}

resp = client.post("/share-grant", json=submission_payload)
assert resp.status_code == 202, resp.text
data = resp.json()
request_id = data["request_id"]
assert data["status"] == "ACCEPTED"
assert data["dispatch_status"] == "DISPATCHED"
assert len(sqs_messages) == 1
sqs_message = sqs_messages[0]

# 2. Simulate Databricks Service processing SQS message
dbx_script = '''
import sys
import json

dbx_dir = sys.argv[1]
sqs_json = sys.argv[2]

sys.path.insert(0, dbx_dir)

from application.dto.permission_request_dto import PermissionRequestDTO, PrincipalDTO, ResourceDTO
from adapters.outbound.databricks.unity_catalog_adapter import UnityCatalogAdapter
from application.services.validation_service import ValidationService
from application.services.permission_analyzer import PermissionAnalyzer
from application.services.operation_planner import OperationPlanner
from application.use_cases.grant_permission import GrantPermissionUseCase
from application.use_cases.revoke_permission import RevokePermissionUseCase
from application.workflows.permission_workflow import PermissionWorkflow
from application.ports.outbound.controller_port import ControllerPort

class DirectCallback(ControllerPort):
    def send_callback(self, result):
        return True

msg = json.loads(sqs_json)
callback_spy = DirectCallback()
uc = UnityCatalogAdapter(use_mock=True)
val = ValidationService(uc)
ana = PermissionAnalyzer(uc)
planner = OperationPlanner(val, ana)
grant_uc = GrantPermissionUseCase(uc)
revoke_uc = RevokePermissionUseCase(uc)
workflow = PermissionWorkflow(planner, grant_uc, revoke_uc, callback_spy)

req = PermissionRequestDTO(
    message_version=msg["message_version"],
    request_id=msg["request_id"],
    operation=msg["operation"],
    workspace_id=msg["workspace_id"],
    principal=PrincipalDTO(type=msg["principal"]["type"], name=msg["principal"]["name"]),
    resource=ResourceDTO(type=msg["resource"]["type"], catalog=msg["resource"]["catalog"], schema=msg["resource"]["schema"], name=msg["resource"]["name"]),
    requested_privileges=msg["requested_privileges"],
    correlation_id=msg["correlation_id"]
)
res = workflow.execute(req)

print(json.dumps({
    "event_id": res.event_id,
    "status": res.status,
    "started_at": res.started_at,
    "finished_at": res.finished_at,
    "result": {
        "operation": res.result.operation,
        "resource": res.result.resource,
        "principal": res.result.principal,
        "applied_privileges": res.result.applied_privileges
    } if res.result else None
}))
'''

sub_proc = subprocess.run([py_exec, "-c", dbx_script, dbx_dir, json.dumps(sqs_message)], capture_output=True, text=True)
assert sub_proc.returncode == 0, f"DBX STDERR: {sub_proc.stderr}"
dbx_output = json.loads(sub_proc.stdout.strip())
assert dbx_output["status"] == "SUCCEEDED"

# 3. Deliver Callback to Controller via HTTP
callback_resp = client.post(f"/share-grant/{request_id}/result", json=dbx_output)
assert callback_resp.status_code == 200, callback_resp.text
assert callback_resp.json()["callback_status"] == "ACCEPTED"

# 4. Outbox Publisher processes pending events
published_count = publish_outbox_uc.publish_pending()
assert published_count == 1
assert len(sns_events) == 1
assert sns_events[0]["request_id"] == request_id
assert sns_events[0]["event_type"] == "SHARE_GRANT_COMPLETED"
assert sns_events[0]["execution_status"] == "SUCCEEDED"

# 5. Verify final status via GET /share-grant/{request_id}
status_resp = client.get(f"/share-grant/{request_id}")
assert status_resp.status_code == 200
status_data = status_resp.json()
assert status_data["execution_status"] == "SUCCEEDED"
assert status_data["notification_status"] == "PUBLISHED"
assert status_data["result"]["applied_privileges"] == ["SELECT"]

print("SUCCESS")
"""

    res = subprocess.run([py_exec, "-c", script, controller_dir, dbx_dir, py_exec], capture_output=True, text=True)
    assert res.returncode == 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "SUCCESS" in res.stdout
