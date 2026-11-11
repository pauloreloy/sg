from typing import List
from application.ports.outbound.unity_catalog_port import UnityCatalogPort
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege


class RevokePermissionUseCase:
    def __init__(self, unity_catalog_port: UnityCatalogPort):
        self.unity_catalog_port = unity_catalog_port

    def execute(
        self,
        resource: Resource,
        principal: Principal,
        privileges_to_revoke: List[Privilege],
    ) -> List[Privilege]:
        if not privileges_to_revoke:
            return []
        return self.unity_catalog_port.revoke(resource, principal, privileges_to_revoke)
