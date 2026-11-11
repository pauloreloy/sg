from enum import Enum


class OperationType(str, Enum):
    GRANT = "GRANT"
    REVOKE = "REVOKE"
