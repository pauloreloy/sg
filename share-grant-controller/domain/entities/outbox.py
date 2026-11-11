from dataclasses import dataclass
from typing import Any, Dict, Optional
from domain.enums import NotificationStatus


@dataclass
class OutboxItemEntity:
    event_id: str
    request_id: str
    event_type: str
    status: NotificationStatus
    created_at: str
    payload: Dict[str, Any]
    updated_at: Optional[str] = None
