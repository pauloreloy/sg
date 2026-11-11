import logging
from typing import Any
import boto3

from adapters.inbound.sqs.permission_request_consumer import PermissionRequestConsumer
from adapters.outbound.controller.controller_http_adapter import ControllerHttpAdapter
from adapters.outbound.databricks.unity_catalog_adapter import UnityCatalogAdapter
from application.services.operation_planner import OperationPlanner
from application.services.permission_analyzer import PermissionAnalyzer
from application.services.validation_service import ValidationService
from application.use_cases.grant_permission import GrantPermissionUseCase
from application.use_cases.process_request import ProcessRequestUseCase
from application.use_cases.revoke_permission import RevokePermissionUseCase
from application.workflows.permission_workflow import PermissionWorkflow
from infrastructure.config import Settings, settings
from infrastructure.logging import setup_logging

logger = logging.getLogger(__name__)


def _create_boto3_client(service_name: str, config: Settings) -> Any:
    kwargs: dict = {
        "region_name": config.aws_region,
        "aws_access_key_id": config.aws_access_key_id,
        "aws_secret_access_key": config.aws_secret_access_key,
    }
    if config.is_localstack_enabled:
        kwargs["endpoint_url"] = config.localstack_endpoint.strip()
    return boto3.client(service_name, **kwargs)


def bootstrap_service(config: Settings = settings) -> PermissionRequestConsumer:
    """Composition Root: wires concrete clients, outbound adapters, services, use cases, workflow, and inbound consumer."""
    setup_logging(level=config.log_level)

    logger.info("Bootstrapping analytics-share-grant-dbx-service...")
    logger.info(
        f"LocalStack integration: {'ENABLED (' + config.localstack_endpoint + ')' if config.is_localstack_enabled else 'DISABLED (AWS)'}"
    )

    # 1. Concrete SDK Clients
    sqs_client = _create_boto3_client("sqs", config)

    # 2. Outbound Adapters
    unity_catalog_adapter = UnityCatalogAdapter(config=config)
    controller_adapter = ControllerHttpAdapter(config=config)

    # 3. Application Services & Use Cases
    validation_service = ValidationService(unity_catalog_port=unity_catalog_adapter)
    permission_analyzer = PermissionAnalyzer(unity_catalog_port=unity_catalog_adapter)
    planner = OperationPlanner(
        validation_service=validation_service,
        permission_analyzer=permission_analyzer,
    )
    grant_use_case = GrantPermissionUseCase(unity_catalog_port=unity_catalog_adapter)
    revoke_use_case = RevokePermissionUseCase(unity_catalog_port=unity_catalog_adapter)

    # 4. Application Workflow
    workflow = PermissionWorkflow(
        planner=planner,
        grant_use_case=grant_use_case,
        revoke_use_case=revoke_use_case,
        controller_port=controller_adapter,
    )

    # 5. Inbound Use Case
    process_request_use_case = ProcessRequestUseCase(workflow=workflow)

    # 6. Inbound Adapter (SQS Consumer) with injected SQS client
    consumer = PermissionRequestConsumer(
        process_request_port=process_request_use_case,
        sqs_client=sqs_client,
        queue_name=config.sqs_requests_queue_name,
        queue_url=config.sqs_requests_queue_url,
        poll_wait_time_seconds=config.sqs_poll_wait_time_seconds,
        visibility_timeout_seconds=config.sqs_visibility_timeout_seconds,
    )

    return consumer
