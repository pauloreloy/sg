from abc import ABC, abstractmethod


class ReconcileDispatchesPort(ABC):
    """Inbound Port for reconciling unconfirmed/stuck dispatches."""

    @abstractmethod
    def reconcile(self) -> int:
        raise NotImplementedError
