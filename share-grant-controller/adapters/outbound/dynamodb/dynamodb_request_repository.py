import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from application.ports.outbound.request_repository_port import RequestRepositoryPort
from domain.entities.request import (
    PrincipalEntity,
    ResourceEntity,
    ShareGrantRequestEntity,
)
from domain.enums import DispatchStatus, ExecutionStatus, NotificationStatus, OperationType
from domain.exceptions import InvalidStateTransitionException, RepositoryException

logger = logging.getLogger(__name__)


class DynamoDBRequestRepository(RequestRepositoryPort):
    def __init__(self, dynamodb_resource: Any, table_name: str = "share-grant-requests"):
        self.resource = dynamodb_resource
        self.table_name = table_name
        self.table = dynamodb_resource.Table(table_name)

    def save_initial(self, request: ShareGrantRequestEntity) -> None:
        item = {
            "request_id": request.request_id,
            "operation": request.operation.value,
            "target": request.target,
            "workspace_id": request.workspace_id,
            "principal": {
                "type": request.principal.type,
                "name": request.principal.name,
            },
            "resource": {
                "type": request.resource.type,
                "catalog": request.resource.catalog,
                "schema": request.resource.schema,
                "name": request.resource.name,
            },
            "requested_privileges": request.requested_privileges,
            "dispatch_status": request.dispatch_status.value,
            "execution_status": request.execution_status.value,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            "dispatch_attempts": request.dispatch_attempts,
        }

        if request.notification_status:
            item["notification_status"] = request.notification_status.value
        if request.correlation_id:
            item["correlation_id"] = request.correlation_id
        if request.idempotency_key:
            item["idempotency_key"] = request.idempotency_key

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(request_id)",
            )
            logger.info(f"Saved initial request {request.request_id} in DynamoDB")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise InvalidStateTransitionException(
                    f"Request {request.request_id} already exists in DynamoDB."
                )
            logger.error(f"Failed to save initial request {request.request_id}: {e}")
            raise RepositoryException(f"Failed to save initial request: {e}")

    def update_dispatch(
        self,
        request_id: str,
        new_status: DispatchStatus,
        expected_status: Optional[DispatchStatus] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        update_expr = "SET dispatch_status = :new_s, updated_at = :now, dispatch_attempts = dispatch_attempts + :one"
        expr_values: Dict[str, Any] = {
            ":new_s": new_status.value,
            ":now": now,
            ":one": 1,
        }

        condition_expr = "attribute_exists(request_id)"
        if expected_status:
            condition_expr += " AND dispatch_status = :exp_s"
            expr_values[":exp_s"] = expected_status.value

        try:
            self.table.update_item(
                Key={"request_id": request_id},
                UpdateExpression=update_expr,
                ConditionExpression=condition_expr,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"Updated request {request_id} dispatch_status to {new_status.value}")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise InvalidStateTransitionException(
                    f"Conditional update failed for request {request_id}. Expected status {expected_status}."
                )
            logger.error(f"Failed to update dispatch status for {request_id}: {e}")
            raise RepositoryException(f"Failed to update dispatch status: {e}")

    def get_by_id(self, request_id: str) -> Optional[ShareGrantRequestEntity]:
        try:
            response = self.table.get_item(Key={"request_id": request_id})
            item = response.get("Item")
            if not item:
                return None
            return self._item_to_entity(item)
        except ClientError as e:
            logger.error(f"Failed to fetch request {request_id}: {e}")
            raise RepositoryException(f"Failed to get request: {e}")

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ShareGrantRequestEntity]:
        try:
            response = self.table.query(
                IndexName="idempotency_key-index",
                KeyConditionExpression=Key("idempotency_key").eq(idempotency_key),
            )
            items = response.get("Items", [])
            if items:
                return self._item_to_entity(items[0])
            return None
        except ClientError as e:
            logger.warning(f"GSI query failed ({e}), scanning for idempotency_key")
            scan_resp = self.table.scan(
                FilterExpression=Attr("idempotency_key").eq(idempotency_key)
            )
            items = scan_resp.get("Items", [])
            if items:
                return self._item_to_entity(items[0])
            return None

    def get_stuck_pending(self, threshold_seconds: int) -> List[ShareGrantRequestEntity]:
        now_ts = datetime.now(timezone.utc).timestamp()
        try:
            response = self.table.scan(
                FilterExpression=Attr("dispatch_status").eq(DispatchStatus.PENDING.value)
            )
            stuck = []
            for item in response.get("Items", []):
                req = self._item_to_entity(item)
                created_dt = datetime.fromisoformat(req.created_at)
                if (now_ts - created_dt.timestamp()) > threshold_seconds:
                    stuck.append(req)
            return stuck
        except Exception as e:
            logger.error(f"Failed to scan stuck pending requests: {e}")
            return []

    def _item_to_entity(self, item: Dict[str, Any]) -> ShareGrantRequestEntity:
        return ShareGrantRequestEntity(
            request_id=item["request_id"],
            operation=OperationType(item["operation"]),
            workspace_id=item["workspace_id"],
            principal=PrincipalEntity(
                type=item["principal"]["type"],
                name=item["principal"]["name"],
            ),
            resource=ResourceEntity(
                type=item["resource"]["type"],
                catalog=item["resource"]["catalog"],
                schema=item["resource"]["schema"],
                name=item["resource"]["name"],
            ),
            requested_privileges=item.get("requested_privileges", []),
            target=item.get("target", "DATABRICKS"),
            dispatch_status=DispatchStatus(item["dispatch_status"]),
            execution_status=ExecutionStatus(item["execution_status"]),
            notification_status=NotificationStatus(item["notification_status"])
            if item.get("notification_status")
            else None,
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            correlation_id=item.get("correlation_id"),
            idempotency_key=item.get("idempotency_key"),
            dispatch_attempts=int(item.get("dispatch_attempts", 0)),
            result=item.get("result"),
            error=item.get("error"),
        )
