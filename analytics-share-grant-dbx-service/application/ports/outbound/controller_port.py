from abc import ABC, abstractmethod
from application.dto.operation_result_dto import OperationResultDTO


class ControllerPort(ABC):
    """Outbound Port for sending execution results back to the Controller via HTTP callback."""

    @abstractmethod
    def send_callback(self, result: OperationResultDTO) -> bool:
        """Sends the operation result to the Controller's callback endpoint."""
        raise NotImplementedError
