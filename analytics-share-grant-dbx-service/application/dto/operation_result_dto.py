from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AppliedResultDTO:
    operation: str
    resource: str
    principal: str
    applied_privileges: List[str]


@dataclass(frozen=True)
class OperationErrorDTO:
    code: str
    message: str


@dataclass(frozen=True)
class OperationResultDTO:
    event_id: str
    request_id: str
    status: str  # "SUCCEEDED" or "FAILED"
    started_at: str
    finished_at: str
    result: Optional[AppliedResultDTO] = None
    error: Optional[OperationErrorDTO] = None
