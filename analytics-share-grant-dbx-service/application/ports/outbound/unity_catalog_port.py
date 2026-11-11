from abc import ABC, abstractmethod
from typing import List, Set
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege


class UnityCatalogPort(ABC):
    """Outbound Port for Databricks Unity Catalog interactions."""

    @abstractmethod
    def principal_exists(self, principal: Principal) -> bool:
        """Checks if the principal exists in the workspace."""
        raise NotImplementedError

    @abstractmethod
    def resource_exists(self, resource: Resource) -> bool:
        """Checks if the catalog/schema/table/view resource exists in Unity Catalog."""
        raise NotImplementedError

    @abstractmethod
    def list_permissions(self, resource: Resource, principal: Principal) -> Set[Privilege]:
        """Lists current active privileges for the principal on the resource."""
        raise NotImplementedError

    @abstractmethod
    def grant(
        self, resource: Resource, principal: Principal, privileges: List[Privilege]
    ) -> List[Privilege]:
        """Grants the specified privileges on the resource to the principal."""
        raise NotImplementedError

    @abstractmethod
    def revoke(
        self, resource: Resource, principal: Principal, privileges: List[Privilege]
    ) -> List[Privilege]:
        """Revokes the specified privileges on the resource from the principal."""
        raise NotImplementedError
