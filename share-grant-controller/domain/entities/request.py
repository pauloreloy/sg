from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from domain.enums import DispatchStatus, ExecutionStatus, NotificationStatus, OperationType


@dataclass(frozen=True)
class PrincipalEntity:
    type: str
    name: str


@dataclass(frozen=True)
class ResourceEntity:
    type: str
    catalog: str
    schema: str
    name: str

    @property
    def full_name(self) -> str:
        if self.schema and self.name:
            return f"{self.catalog}.{self.schema}.{self.name}"
        elif self.schema:
            return f"{self.catalog}.{self.schema}"
        return self.catalog


@dataclass
class ShareGrantRequestEntity:
    request_id: str
    operation: OperationType
    workspace_id: str
    principal: PrincipalEntity
    resource: ResourceEntity
    requested_privileges: List[str]
    target: str = "DATABRICKS"
    dispatch_status: DispatchStatus = DispatchStatus.PENDING
    execution_status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    notification_status: Optional[NotificationStatus] = None
    created_at: str = ""
    updated_at: str = ""
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    dispatch_attempts: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
