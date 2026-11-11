from abc import ABC, abstractmethod
from typing import Any, Dict


class MessageDispatcherPort(ABC):
    """Outbound Port for dispatching grant/revoke messages to SQS."""

    @abstractmethod
    def dispatch(self, message: Dict[str, Any]) -> str:
        """Sends message to SQS queue. Returns external message identifier."""
        raise NotImplementedError
