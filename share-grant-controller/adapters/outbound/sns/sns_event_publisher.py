import json
import logging
from typing import Any, Dict, Optional
from botocore.exceptions import ClientError

from application.ports.outbound.event_publisher_port import EventPublisherPort
from domain.exceptions import RepositoryException

logger = logging.getLogger(__name__)


class SNSEventPublisher(EventPublisherPort):
    def __init__(self, sns_client: Any, topic_arn: str):
        self.sns = sns_client
        self.topic_arn = topic_arn

    def publish(
        self,
        event_payload: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> str:
        try:
            message_body = json.dumps(event_payload)
            msg_attrs = {}
            if attributes:
                for k, v in attributes.items():
                    msg_attrs[k] = {"DataType": "String", "StringValue": str(v)}

            if "event_type" in event_payload:
                msg_attrs["event_type"] = {
                    "DataType": "String",
                    "StringValue": str(event_payload["event_type"]),
                }
            if "event_id" in event_payload:
                msg_attrs["event_id"] = {
                    "DataType": "String",
                    "StringValue": str(event_payload["event_id"]),
                }

            response = self.sns.publish(
                TopicArn=self.topic_arn,
                Message=message_body,
                MessageAttributes=msg_attrs,
            )
            message_id = response.get("MessageId", "")
            logger.info(
                f"Published event {event_payload.get('event_id')} to SNS HUB (MessageId: {message_id})"
            )
            return message_id
        except ClientError as e:
            logger.error(f"Failed to publish event to SNS: {e}")
            raise RepositoryException(f"Failed to publish to SNS: {e}")
