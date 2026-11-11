from typing import List, Set
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType
from domain.exceptions.domain_exceptions import InvalidPrivilegeException


class PermissionDomainService:
    ALLOWED_PRIVILEGES_MAP = {
        ResourceType.CATALOG: {Privilege.USE_CATALOG, Privilege.ALL_PRIVILEGES},
        ResourceType.SCHEMA: {Privilege.USE_SCHEMA, Privilege.ALL_PRIVILEGES},
        ResourceType.TABLE: {
            Privilege.SELECT,
            Privilege.MODIFY,
            Privilege.READ_METADATA,
            Privilege.ALL_PRIVILEGES,
        },
        ResourceType.VIEW: {
            Privilege.SELECT,
            Privilege.READ_METADATA,
            Privilege.ALL_PRIVILEGES,
        },
    }

    @classmethod
    def validate_privileges_for_resource(
        cls, resource: Resource, privileges: List[Privilege]
    ) -> None:
        """Ensures the requested privileges are applicable to the resource type."""
        allowed = cls.ALLOWED_PRIVILEGES_MAP.get(resource.type, set())
        for priv in privileges:
            if priv not in allowed:
                raise InvalidPrivilegeException(
                    privilege=priv.value, resource_type=resource.type.value
                )

    @staticmethod
    def calculate_grant_diff(
        requested: Set[Privilege], current: Set[Privilege]
    ) -> Set[Privilege]:
        """Calculates which privileges actually need to be granted."""
        if Privilege.ALL_PRIVILEGES in current:
            return set()
        return requested - current

    @staticmethod
    def calculate_revoke_diff(
        requested: Set[Privilege], current: Set[Privilege]
    ) -> Set[Privilege]:
        """Calculates which privileges actually need to be revoked."""
        return requested.intersection(current)
