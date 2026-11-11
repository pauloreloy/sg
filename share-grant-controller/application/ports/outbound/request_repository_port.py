from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.request import ShareGrantRequestEntity
from domain.enums import DispatchStatus


class RequestRepositoryPort(ABC):
    """Outbound Port for persisting and querying ShareGrantRequest entities."""

    @abstractmethod
    def save_initial(self, request: ShareGrantRequestEntity) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_dispatch(
        self,
        request_id: str,
        new_status: DispatchStatus,
        expected_status: Optional[DispatchStatus] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, request_id: str) -> Optional[ShareGrantRequestEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ShareGrantRequestEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_stuck_pending(self, threshold_seconds: int) -> List[ShareGrantRequestEntity]:
        raise NotImplementedError
