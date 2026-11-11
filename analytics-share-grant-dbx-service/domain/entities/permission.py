from dataclasses import dataclass, field
from typing import Set
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege


@dataclass
class Permission:
    resource: Resource
    principal: Principal
    privileges: Set[Privilege] = field(default_factory=set)

    def add_privilege(self, privilege: Privilege) -> None:
        self.privileges.add(privilege)

    def remove_privilege(self, privilege: Privilege) -> None:
        self.privileges.discard(privilege)

    def has_privilege(self, privilege: Privilege) -> bool:
        return privilege in self.privileges or Privilege.ALL_PRIVILEGES in self.privileges
