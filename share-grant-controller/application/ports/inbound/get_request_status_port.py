from abc import ABC, abstractmethod
from typing import Optional
from application.dto.request_status_dto import RequestStatusDTO


class GetRequestStatusPort(ABC):
    """Inbound Port for checking the status of a request."""

    @abstractmethod
    def get_status(self, request_id: str) -> Optional[RequestStatusDTO]:
        raise NotImplementedError
