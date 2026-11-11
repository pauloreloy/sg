from dataclasses import dataclass
from typing import List, Set
from application.services.permission_analyzer import PermissionAnalyzer
from application.services.validation_service import ValidationService
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.operation_type import OperationType
from domain.enums.privilege import Privilege


@dataclass(frozen=True)
class OperationPlan:
    operation: OperationType
    resource: Resource
    principal: Principal
    privileges_to_apply: List[Privilege]
    is_noop: bool


class OperationPlanner:
    def __init__(
        self,
        validation_service: ValidationService,
        permission_analyzer: PermissionAnalyzer,
    ):
        self.validation_service = validation_service
        self.permission_analyzer = permission_analyzer

    def create_plan(
        self,
        operation: OperationType,
        resource: Resource,
        principal: Principal,
        requested_privileges: List[Privilege],
    ) -> OperationPlan:
        # Validate existence and privilege compatibility
        self.validation_service.validate_request(principal, resource, requested_privileges)

        if operation == OperationType.GRANT:
            diff = self.permission_analyzer.analyze_grant_diff(
                resource, principal, requested_privileges
            )
        else:
            diff = self.permission_analyzer.analyze_revoke_diff(
                resource, principal, requested_privileges
            )

        privileges_to_apply = sorted(list(diff), key=lambda p: p.value)
        is_noop = len(privileges_to_apply) == 0

        return OperationPlan(
            operation=operation,
            resource=resource,
            principal=principal,
            privileges_to_apply=privileges_to_apply,
            is_noop=is_noop,
        )
