from enum import Enum


class DispatchStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    DISPATCH_FAILED = "DISPATCH_FAILED"


class ExecutionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class OperationType(str, Enum):
    GRANT = "GRANT"
    REVOKE = "REVOKE"
