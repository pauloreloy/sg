from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RequestStatusDTO:
    request_id: str
    operation: str
    target: str
    workspace_id: str
    principal: Dict[str, str]
    resource: Dict[str, str]
    requested_privileges: List[str]
    dispatch_status: str
    execution_status: str
    notification_status: Optional[str]
    created_at: str
    updated_at: str
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
