from abc import ABC, abstractmethod


class PublishOutboxPort(ABC):
    """Inbound Port for publishing pending outbox events."""

    @abstractmethod
    def publish_pending(self, limit: int = 50) -> int:
        raise NotImplementedError
