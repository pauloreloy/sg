from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PrincipalHttpSchema(BaseModel):
    type: str
    name: str


class ResourceHttpSchema(BaseModel):
    type: str
    catalog: str
    schema_name: str = Field(alias="schema")
    name: str

    model_config = {
        "populate_by_name": True,
    }


class MetadataHttpSchema(BaseModel):
    requested_by: Optional[str] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class SubmissionHttpPayload(BaseModel):
    operation: str
    workspace_id: str
    principal: PrincipalHttpSchema
    resource: ResourceHttpSchema
    requested_privileges: List[str]
    metadata: Optional[MetadataHttpSchema] = None


class SubmissionHttpResponse(BaseModel):
    request_id: str
    status: str
    dispatch_status: str


class CallbackResultHttpSchema(BaseModel):
    operation: str
    resource: str
    principal: str
    applied_privileges: List[str]


class CallbackErrorHttpSchema(BaseModel):
    code: str
    message: str


class CallbackHttpPayload(BaseModel):
    event_id: str
    status: str
    started_at: str
    finished_at: str
    result: Optional[CallbackResultHttpSchema] = None
    error: Optional[CallbackErrorHttpSchema] = None


class CallbackHttpResponse(BaseModel):
    request_id: str
    callback_status: str


class RequestStatusHttpResponse(BaseModel):
    request_id: str
    operation: str
    target: str
    workspace_id: str
    principal: Dict[str, str]
    resource: Dict[str, str]
    requested_privileges: List[str]
    dispatch_status: str
    execution_status: str
    notification_status: Optional[str] = None
    created_at: str
    updated_at: str
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
