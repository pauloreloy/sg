import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from application.ports.outbound.outbox_repository_port import OutboxRepositoryPort
from domain.entities.outbox import OutboxItemEntity
from domain.enums import ExecutionStatus, NotificationStatus
from domain.exceptions import RepositoryException, RequestNotFoundException

logger = logging.getLogger(__name__)


class DynamoDBOutboxRepository(OutboxRepositoryPort):
    def __init__(
        self,
        dynamodb_client: Any,
        dynamodb_resource: Any,
        requests_table_name: str = "share-grant-requests",
        outbox_table_name: str = "share-grant-outbox",
    ):
        self.client = dynamodb_client
        self.resource = dynamodb_resource
        self.requests_table_name = requests_table_name
        self.outbox_table_name = outbox_table_name
        self.requests_table = dynamodb_resource.Table(requests_table_name)
        self.outbox_table = dynamodb_resource.Table(outbox_table_name)

    def save_callback_and_outbox(
        self,
        request_id: str,
        outbox_item: OutboxItemEntity,
        status: ExecutionStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        request_update_expr = (
            "SET execution_status = :st, notification_status = :notif, updated_at = :now"
        )
        expr_attr_values: Dict[str, Any] = {
            ":st": {"S": status.value},
            ":notif": {"S": NotificationStatus.PENDING.value},
            ":now": {"S": now},
            ":term_succeeded": {"S": ExecutionStatus.SUCCEEDED.value},
            ":term_failed": {"S": ExecutionStatus.FAILED.value},
        }

        if result:
            request_update_expr += ", #res = :res"
            expr_attr_values[":res"] = self._dict_to_dynamo_map(result)

        if error:
            request_update_expr += ", #err = :err"
            expr_attr_values[":err"] = self._dict_to_dynamo_map(error)

        expr_attr_names = {}
        if result:
            expr_attr_names["#res"] = "result"
        if error:
            expr_attr_names["#err"] = "error"

        request_condition = (
            "attribute_exists(request_id) AND execution_status <> :term_succeeded AND execution_status <> :term_failed"
        )

        outbox_put_item = {
            "event_id": {"S": outbox_item.event_id},
            "request_id": {"S": request_id},
            "event_type": {"S": outbox_item.event_type},
            "status": {"S": NotificationStatus.PENDING.value},
            "created_at": {"S": now},
            "updated_at": {"S": now},
            "payload": self._dict_to_dynamo_map(outbox_item.payload),
        }

        transact_items = [
            {
                "Update": {
                    "TableName": self.requests_table_name,
                    "Key": {"request_id": {"S": request_id}},
                    "UpdateExpression": request_update_expr,
                    "ConditionExpression": request_condition,
                    "ExpressionAttributeValues": expr_attr_values,
                    **({"ExpressionAttributeNames": expr_attr_names} if expr_attr_names else {}),
                }
            },
            {
                "Put": {
                    "TableName": self.outbox_table_name,
                    "Item": outbox_put_item,
                    "ConditionExpression": "attribute_not_exists(event_id)",
                }
            },
        ]

        try:
            self.client.transact_write_items(TransactItems=transact_items)
            logger.info(
                f"Atomic transaction completed for request {request_id} with outbox event {outbox_item.event_id}"
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            logger.warning(f"Transaction failed for callback on {request_id}: {code}")

            # Check if request exists
            resp = self.requests_table.get_item(Key={"request_id": request_id})
            existing = resp.get("Item")
            if not existing:
                raise RequestNotFoundException(request_id)

            # If already in terminal state, idempotent acceptance
            if existing.get("execution_status") in [
                ExecutionStatus.SUCCEEDED.value,
                ExecutionStatus.FAILED.value,
            ]:
                logger.info(
                    f"Request {request_id} is already in terminal state {existing.get('execution_status')}. Accepted idempotently."
                )
                return

            raise RepositoryException(f"Transaction failed: {e}")

    def get_pending_items(self, limit: int = 50) -> List[OutboxItemEntity]:
        try:
            response = self.outbox_table.query(
                IndexName="status-created_at-index",
                KeyConditionExpression=Key("status").eq(NotificationStatus.PENDING.value),
                Limit=limit,
            )
            items = response.get("Items", [])
            return [self._item_to_entity(item) for item in items]
        except ClientError as e:
            logger.warning(f"Outbox GSI query failed ({e}), falling back to scan")
            scan_resp = self.outbox_table.scan(
                FilterExpression=Attr("status").eq(NotificationStatus.PENDING.value),
                Limit=limit,
            )
            items = scan_resp.get("Items", [])
            return [self._item_to_entity(item) for item in items]

    def mark_published(self, event_id: str, request_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.outbox_table.update_item(
                Key={"event_id": event_id},
                UpdateExpression="SET #st = :pub, updated_at = :now",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":pub": NotificationStatus.PUBLISHED.value,
                    ":now": now,
                },
            )
            self.requests_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET notification_status = :pub, updated_at = :now",
                ExpressionAttributeValues={
                    ":pub": NotificationStatus.PUBLISHED.value,
                    ":now": now,
                },
            )
            logger.info(f"Marked event {event_id} and request {request_id} as PUBLISHED")
        except ClientError as e:
            logger.error(f"Failed to mark outbox {event_id} as published: {e}")
            raise RepositoryException(f"Failed to mark outbox published: {e}")

    def _item_to_entity(self, item: Dict[str, Any]) -> OutboxItemEntity:
        return OutboxItemEntity(
            event_id=item["event_id"],
            request_id=item["request_id"],
            event_type=item["event_type"],
            status=NotificationStatus(item["status"]),
            created_at=item["created_at"],
            updated_at=item.get("updated_at"),
            payload=item.get("payload", {}),
        )

    def _dict_to_dynamo_map(self, d: Dict[str, Any]) -> Dict[str, Any]:
        m = {}
        for k, v in d.items():
            if isinstance(v, str):
                m[k] = {"S": v}
            elif isinstance(v, bool):
                m[k] = {"BOOL": v}
            elif isinstance(v, (int, float)):
                m[k] = {"N": str(v)}
            elif isinstance(v, list):
                if all(isinstance(x, str) for x in v):
                    m[k] = {"SS": v} if v else {"L": []}
                else:
                    m[k] = {"L": [self._val_to_dynamo(x) for x in v]}
            elif isinstance(v, dict):
                m[k] = self._dict_to_dynamo_map(v)
            elif v is None:
                m[k] = {"NULL": True}
        return {"M": m}

    def _val_to_dynamo(self, v: Any) -> Dict[str, Any]:
        if isinstance(v, str):
            return {"S": v}
        elif isinstance(v, bool):
            return {"BOOL": v}
        elif isinstance(v, (int, float)):
            return {"N": str(v)}
        elif isinstance(v, dict):
            return self._dict_to_dynamo_map(v)
        elif v is None:
            return {"NULL": True}
        return {"S": str(v)}
