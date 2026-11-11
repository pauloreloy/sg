from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.entities.outbox import OutboxItemEntity
from domain.enums import ExecutionStatus


class OutboxRepositoryPort(ABC):
    """Outbound Port for transactional Outbox persistence and status updates."""

    @abstractmethod
    def save_callback_and_outbox(
        self,
        request_id: str,
        outbox_item: OutboxItemEntity,
        status: ExecutionStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Atomically updates request terminal state and writes an outbox record."""
        raise NotImplementedError

    @abstractmethod
    def get_pending_items(self, limit: int = 50) -> List[OutboxItemEntity]:
        raise NotImplementedError

    @abstractmethod
    def mark_published(self, event_id: str, request_id: str) -> None:
        raise NotImplementedError
