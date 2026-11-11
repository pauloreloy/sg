from abc import ABC, abstractmethod
from application.dto.callback_dto import CallbackRequestDTO, CallbackResponseDTO


class ProcessCallbackPort(ABC):
    """Inbound Port for processing callbacks from Databricks service."""

    @abstractmethod
    def process(self, callback: CallbackRequestDTO) -> CallbackResponseDTO:
        raise NotImplementedError
