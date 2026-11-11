from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class EventPublisherPort(ABC):
    """Outbound Port for publishing completed events to SNS HUB."""

    @abstractmethod
    def publish(
        self,
        event_payload: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> str:
        """Publishes event to SNS HUB. Returns external message identifier."""
        raise NotImplementedError
