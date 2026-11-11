from typing import List, Set
from application.ports.outbound.unity_catalog_port import UnityCatalogPort
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege
from domain.services.permission_domain_service import PermissionDomainService


class PermissionAnalyzer:
    def __init__(self, unity_catalog_port: UnityCatalogPort):
        self.unity_catalog_port = unity_catalog_port

    def get_current_privileges(
        self, resource: Resource, principal: Principal
    ) -> Set[Privilege]:
        return self.unity_catalog_port.list_permissions(resource, principal)

    def analyze_grant_diff(
        self,
        resource: Resource,
        principal: Principal,
        requested: List[Privilege],
    ) -> Set[Privilege]:
        current = self.get_current_privileges(resource, principal)
        return PermissionDomainService.calculate_grant_diff(set(requested), current)

    def analyze_revoke_diff(
        self,
        resource: Resource,
        principal: Principal,
        requested: List[Privilege],
    ) -> Set[Privilege]:
        current = self.get_current_privileges(resource, principal)
        return PermissionDomainService.calculate_revoke_diff(set(requested), current)
