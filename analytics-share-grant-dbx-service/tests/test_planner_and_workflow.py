from unittest.mock import MagicMock
import pytest
from application.dto.permission_request_dto import (
    PermissionRequestDTO,
    PrincipalDTO,
    ResourceDTO,
)
from application.ports.outbound.controller_port import ControllerPort
from application.ports.outbound.unity_catalog_port import UnityCatalogPort
from application.services.operation_planner import OperationPlanner
from application.services.permission_analyzer import PermissionAnalyzer
from application.services.validation_service import ValidationService
from application.use_cases.grant_permission import GrantPermissionUseCase
from application.use_cases.revoke_permission import RevokePermissionUseCase
from application.workflows.permission_workflow import PermissionWorkflow
from domain.enums.privilege import Privilege


@pytest.fixture
def workflow_setup():
    uc_port = MagicMock(spec=UnityCatalogPort)
    controller_port = MagicMock(spec=ControllerPort)

    validation_service = ValidationService(unity_catalog_port=uc_port)
    analyzer = PermissionAnalyzer(unity_catalog_port=uc_port)
    planner = OperationPlanner(validation_service=validation_service, permission_analyzer=analyzer)
    grant_use_case = GrantPermissionUseCase(unity_catalog_port=uc_port)
    revoke_use_case = RevokePermissionUseCase(unity_catalog_port=uc_port)

    workflow = PermissionWorkflow(
        planner=planner,
        grant_use_case=grant_use_case,
        revoke_use_case=revoke_use_case,
        controller_port=controller_port,
    )

    return workflow, uc_port, controller_port


def test_workflow_grant_success(workflow_setup):
    workflow, uc_port, controller_port = workflow_setup

    uc_port.principal_exists.return_value = True
    uc_port.resource_exists.return_value = True
    uc_port.list_permissions.return_value = set()  # Currently no permissions
    uc_port.grant.return_value = [Privilege.SELECT]

    request = PermissionRequestDTO(
        message_version="1",
        request_id="req-1",
        operation="GRANT",
        workspace_id="ws-1",
        principal=PrincipalDTO(type="GROUP", name="analytics_readers"),
        resource=ResourceDTO(type="TABLE", catalog="shared", schema="sales", name="orders"),
        requested_privileges=["SELECT"],
    )

    result = workflow.execute(request)

    assert result.status == "SUCCEEDED"
    assert result.request_id == "req-1"
    assert result.result.applied_privileges == ["SELECT"]

    uc_port.grant.assert_called_once()
    controller_port.send_callback.assert_called_once_with(result)


def test_workflow_grant_idempotent(workflow_setup):
    workflow, uc_port, controller_port = workflow_setup

    uc_port.principal_exists.return_value = True
    uc_port.resource_exists.return_value = True
    uc_port.list_permissions.return_value = {Privilege.SELECT}  # Already granted!

    request = PermissionRequestDTO(
        message_version="1",
        request_id="req-2",
        operation="GRANT",
        workspace_id="ws-1",
        principal=PrincipalDTO(type="GROUP", name="analytics_readers"),
        resource=ResourceDTO(type="TABLE", catalog="shared", schema="sales", name="orders"),
        requested_privileges=["SELECT"],
    )

    result = workflow.execute(request)

    assert result.status == "SUCCEEDED"
    # uc_port.grant should NOT be called since privilege was already granted!
    uc_port.grant.assert_not_called()
    assert result.result.applied_privileges == ["SELECT"]
    controller_port.send_callback.assert_called_once()


def test_workflow_principal_not_found(workflow_setup):
    workflow, uc_port, controller_port = workflow_setup

    uc_port.principal_exists.return_value = False  # Does not exist

    request = PermissionRequestDTO(
        message_version="1",
        request_id="req-3",
        operation="GRANT",
        workspace_id="ws-1",
        principal=PrincipalDTO(type="GROUP", name="unknown_group"),
        resource=ResourceDTO(type="TABLE", catalog="shared", schema="sales", name="orders"),
        requested_privileges=["SELECT"],
    )

    result = workflow.execute(request)

    assert result.status == "FAILED"
    assert result.error.code == "PRINCIPAL_NOT_FOUND"
    uc_port.grant.assert_not_called()
    controller_port.send_callback.assert_called_once_with(result)


def test_workflow_resource_not_found(workflow_setup):
    workflow, uc_port, controller_port = workflow_setup

    uc_port.principal_exists.return_value = True
    uc_port.resource_exists.return_value = False  # Resource does not exist

    request = PermissionRequestDTO(
        message_version="1",
        request_id="req-4",
        operation="GRANT",
        workspace_id="ws-1",
        principal=PrincipalDTO(type="GROUP", name="analytics_readers"),
        resource=ResourceDTO(type="TABLE", catalog="shared", schema="sales", name="unknown_table"),
        requested_privileges=["SELECT"],
    )

    result = workflow.execute(request)

    assert result.status == "FAILED"
    assert result.error.code == "RESOURCE_NOT_FOUND"
    uc_port.grant.assert_not_called()
    controller_port.send_callback.assert_called_once_with(result)


def test_workflow_revoke_success(workflow_setup):
    workflow, uc_port, controller_port = workflow_setup

    uc_port.principal_exists.return_value = True
    uc_port.resource_exists.return_value = True
    uc_port.list_permissions.return_value = {Privilege.SELECT}
    uc_port.revoke.return_value = [Privilege.SELECT]

    request = PermissionRequestDTO(
        message_version="1",
        request_id="req-5",
        operation="REVOKE",
        workspace_id="ws-1",
        principal=PrincipalDTO(type="GROUP", name="analytics_readers"),
        resource=ResourceDTO(type="TABLE", catalog="shared", schema="sales", name="orders"),
        requested_privileges=["SELECT"],
    )

    result = workflow.execute(request)

    assert result.status == "SUCCEEDED"
    uc_port.revoke.assert_called_once()
    assert result.result.applied_privileges == ["SELECT"]
    controller_port.send_callback.assert_called_once()
