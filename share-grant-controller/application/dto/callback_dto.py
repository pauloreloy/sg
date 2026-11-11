from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CallbackResultDTO:
    operation: str
    resource: str
    principal: str
    applied_privileges: List[str]


@dataclass(frozen=True)
class CallbackErrorDTO:
    code: str
    message: str


@dataclass(frozen=True)
class CallbackRequestDTO:
    request_id: str
    event_id: str
    status: str
    started_at: str
    finished_at: str
    result: Optional[CallbackResultDTO] = None
    error: Optional[CallbackErrorDTO] = None


@dataclass(frozen=True)
class CallbackResponseDTO:
    request_id: str
    callback_status: str
