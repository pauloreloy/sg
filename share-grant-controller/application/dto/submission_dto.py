from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PrincipalInputDTO:
    type: str
    name: str


@dataclass(frozen=True)
class ResourceInputDTO:
    type: str
    catalog: str
    schema: str
    name: str


@dataclass(frozen=True)
class SubmissionMetadataDTO:
    requested_by: Optional[str] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class SubmissionRequestDTO:
    operation: str
    workspace_id: str
    principal: PrincipalInputDTO
    resource: ResourceInputDTO
    requested_privileges: List[str]
    metadata: Optional[SubmissionMetadataDTO] = None


@dataclass(frozen=True)
class SubmissionResponseDTO:
    request_id: str
    status: str
    dispatch_status: str
