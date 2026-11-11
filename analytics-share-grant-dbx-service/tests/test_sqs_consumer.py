from unittest.mock import MagicMock
from adapters.inbound.sqs.permission_request_consumer import PermissionRequestConsumer
from application.ports.inbound.process_request_port import ProcessRequestPort


def test_sqs_consumer_parse_and_call_port():
    process_port = MagicMock(spec=ProcessRequestPort)
    sqs_mock = MagicMock()
    consumer = PermissionRequestConsumer(
        process_request_port=process_port,
        sqs_client=sqs_mock,
    )

    raw_message_body = {
        "message_version": "1",
        "request_id": "req-999",
        "operation": "GRANT",
        "workspace_id": "ws-1",
        "principal": {"type": "GROUP", "name": "readers"},
        "resource": {"type": "TABLE", "catalog": "shared", "schema": "sales", "name": "orders"},
        "requested_privileges": ["SELECT"],
        "correlation_id": "corr-999",
    }

    dto = consumer._parse_to_dto(raw_message_body)

    assert dto.request_id == "req-999"
    assert dto.operation == "GRANT"
    assert dto.principal.name == "readers"
    assert dto.resource.name == "orders"
    assert dto.requested_privileges == ["SELECT"]
    assert dto.correlation_id == "corr-999"
