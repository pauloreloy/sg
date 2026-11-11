import json
import logging
from typing import Any, Dict, Optional
from botocore.exceptions import ClientError

from application.ports.outbound.message_dispatcher_port import MessageDispatcherPort
from domain.exceptions import DispatchFailedException

logger = logging.getLogger(__name__)


class SQSMessageDispatcher(MessageDispatcherPort):
    def __init__(
        self,
        sqs_client: Any,
        queue_name: str = "share-grant-requests-queue",
        queue_url: Optional[str] = None,
    ):
        self.sqs = sqs_client
        self.queue_name = queue_name
        self._queue_url: Optional[str] = queue_url

    def get_queue_url(self) -> str:
        if self._queue_url:
            return self._queue_url

        try:
            resp = self.sqs.get_queue_url(QueueName=self.queue_name)
            self._queue_url = resp["QueueUrl"]
            return self._queue_url
        except ClientError as e:
            logger.error(f"Failed to get SQS queue URL for {self.queue_name}: {e}")
            raise DispatchFailedException(f"Failed to resolve SQS Queue URL: {e}")

    def dispatch(self, message: Dict[str, Any]) -> str:
        queue_url = self.get_queue_url()
        try:
            body = json.dumps(message)
            response = self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=body,
                MessageAttributes={
                    "request_id": {
                        "DataType": "String",
                        "StringValue": str(message.get("request_id", "")),
                    },
                    "correlation_id": {
                        "DataType": "String",
                        "StringValue": str(message.get("correlation_id", "")),
                    },
                },
            )
            message_id = response.get("MessageId", "")
            logger.info(
                f"Dispatched message to SQS queue {queue_url} (MessageId: {message_id}, RequestId: {message.get('request_id')})"
            )
            return message_id
        except ClientError as e:
            logger.error(f"Failed to send message to SQS: {e}")
            raise DispatchFailedException(f"Failed to dispatch message to SQS: {e}")
