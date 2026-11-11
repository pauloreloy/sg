from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PrincipalDTO:
    type: str
    name: str


@dataclass(frozen=True)
class ResourceDTO:
    type: str
    catalog: str
    schema: Optional[str] = None
    name: Optional[str] = None


@dataclass(frozen=True)
class PermissionRequestDTO:
    message_version: str
    request_id: str
    operation: str  # "GRANT" or "REVOKE"
    workspace_id: str
    principal: PrincipalDTO
    resource: ResourceDTO
    requested_privileges: List[str]
    correlation_id: Optional[str] = None
