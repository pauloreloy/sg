from typing import List
from application.ports.outbound.unity_catalog_port import UnityCatalogPort
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege
from domain.exceptions.domain_exceptions import (
    PrincipalNotFoundException,
    ResourceNotFoundException,
)
from domain.services.permission_domain_service import PermissionDomainService


class ValidationService:
    def __init__(self, unity_catalog_port: UnityCatalogPort):
        self.unity_catalog_port = unity_catalog_port

    def validate_request(
        self,
        principal: Principal,
        resource: Resource,
        privileges: List[Privilege],
    ) -> None:
        """Validates domain constraints and external resource/principal existence."""
        # 1. Validate privilege compatibility with resource type
        PermissionDomainService.validate_privileges_for_resource(resource, privileges)

        # 2. Check if principal exists
        if not self.unity_catalog_port.principal_exists(principal):
            raise PrincipalNotFoundException(principal.name)

        # 3. Check if resource exists
        if not self.unity_catalog_port.resource_exists(resource):
            raise ResourceNotFoundException(resource.full_name)
