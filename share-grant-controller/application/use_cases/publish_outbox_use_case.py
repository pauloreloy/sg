import logging
from application.ports.inbound.publish_outbox_port import PublishOutboxPort
from application.ports.outbound.event_publisher_port import EventPublisherPort
from application.ports.outbound.outbox_repository_port import OutboxRepositoryPort

logger = logging.getLogger(__name__)


class PublishOutboxUseCase(PublishOutboxPort):
    def __init__(
        self,
        outbox_repository: OutboxRepositoryPort,
        event_publisher: EventPublisherPort,
    ):
        self.outbox_repository = outbox_repository
        self.event_publisher = event_publisher

    def publish_pending(self, limit: int = 50) -> int:
        pending_items = self.outbox_repository.get_pending_items(limit=limit)
        published_count = 0

        for item in pending_items:
            try:
                event_payload = {
                    "event_id": item.event_id,
                    "request_id": item.request_id,
                    "event_type": item.event_type,
                    "created_at": item.created_at,
                    **item.payload,
                }

                self.event_publisher.publish(
                    event_payload=event_payload,
                    attributes={
                        "event_type": item.event_type,
                        "request_id": item.request_id,
                    },
                )

                self.outbox_repository.mark_published(
                    event_id=item.event_id,
                    request_id=item.request_id,
                )
                published_count += 1
            except Exception as e:
                logger.error(
                    f"Error publishing outbox event {item.event_id} for request {item.request_id}: {e}"
                )

        return published_count
