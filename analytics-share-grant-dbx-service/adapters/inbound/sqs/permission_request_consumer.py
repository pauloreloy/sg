import json
import logging
import time
from typing import Any, Optional
from botocore.exceptions import ClientError

from application.dto.permission_request_dto import (
    PermissionRequestDTO,
    PrincipalDTO,
    ResourceDTO,
)
from application.ports.inbound.process_request_port import ProcessRequestPort

logger = logging.getLogger(__name__)


class PermissionRequestConsumer:
    """
    Inbound Adapter that polls Amazon SQS for grant/revoke messages,
    translates them to PermissionRequestDTO, and invokes the Inbound Port.
    """

    def __init__(
        self,
        process_request_port: ProcessRequestPort,
        sqs_client: Any,
        queue_name: str = "share-grant-requests-queue",
        queue_url: Optional[str] = None,
        poll_wait_time_seconds: int = 5,
        visibility_timeout_seconds: int = 30,
    ):
        self.process_request_port = process_request_port
        self.sqs = sqs_client
        self.queue_name = queue_name
        self._queue_url: Optional[str] = queue_url
        self.poll_wait_time_seconds = poll_wait_time_seconds
        self.visibility_timeout_seconds = visibility_timeout_seconds
        self._running = False

    def get_queue_url(self) -> str:
        if self._queue_url:
            return self._queue_url

        try:
            resp = self.sqs.get_queue_url(QueueName=self.queue_name)
            self._queue_url = resp["QueueUrl"]
            return self._queue_url
        except ClientError as e:
            logger.error(f"Failed to resolve SQS queue URL for {self.queue_name}: {e}")
            raise

    def poll_messages(self, max_messages: int = 1) -> None:
        queue_url = self.get_queue_url()

        try:
            response = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=self.poll_wait_time_seconds,
                VisibilityTimeout=self.visibility_timeout_seconds,
                MessageAttributeNames=["All"],
            )
        except Exception as e:
            logger.error(f"Error receiving messages from SQS: {e}")
            time.sleep(2)
            return

        messages = response.get("Messages", [])
        if not messages:
            return

        for msg in messages:
            receipt_handle = msg.get("ReceiptHandle")
            try:
                body = json.loads(msg.get("Body", "{}"))
                logger.info(
                    f"Received message from SQS (MessageId: {msg.get('MessageId')}, RequestId: {body.get('request_id')})"
                )

                dto = self._parse_to_dto(body)
                self.process_request_port.process(dto)

                self.sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                )
                logger.info(f"Deleted message {msg.get('MessageId')} from SQS")

            except Exception as e:
                logger.error(f"Failed processing message {msg.get('MessageId')}: {e}", exc_info=True)

    def start(self) -> None:
        self._running = True
        logger.info(f"Starting SQS Permission Request Consumer on queue: {self.queue_name}")
        while self._running:
            try:
                self.poll_messages()
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop: {e}")
                time.sleep(2)

    def stop(self) -> None:
        self._running = False
        logger.info("Stopping SQS Permission Request Consumer...")

    def _parse_to_dto(self, body: dict) -> PermissionRequestDTO:
        principal_data = body.get("principal", {})
        resource_data = body.get("resource", {})

        return PermissionRequestDTO(
            message_version=str(body.get("message_version", "1")),
            request_id=body["request_id"],
            operation=body["operation"],
            workspace_id=body.get("workspace_id", ""),
            principal=PrincipalDTO(
                type=principal_data.get("type", "GROUP"),
                name=principal_data.get("name", ""),
            ),
            resource=ResourceDTO(
                type=resource_data.get("type", "TABLE"),
                catalog=resource_data.get("catalog", ""),
                schema=resource_data.get("schema"),
                name=resource_data.get("name"),
            ),
            requested_privileges=body.get("requested_privileges", []),
            correlation_id=body.get("correlation_id"),
        )
