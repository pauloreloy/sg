from abc import ABC, abstractmethod
from application.dto.operation_result_dto import OperationResultDTO
from application.dto.permission_request_dto import PermissionRequestDTO


class ProcessRequestPort(ABC):
    """Inbound Port to execute a Grant/Revoke permission request."""

    @abstractmethod
    def process(self, request: PermissionRequestDTO) -> OperationResultDTO:
        """Processes the request and returns the operation result."""
        raise NotImplementedError
