import logging
from contextlib import asynccontextmanager
from typing import Any
import boto3
from fastapi import FastAPI

from adapters.inbound.http.background_workers import BackgroundWorkers
from adapters.inbound.http.router import create_router
from adapters.outbound.dynamodb.dynamodb_outbox_repository import DynamoDBOutboxRepository
from adapters.outbound.dynamodb.dynamodb_request_repository import DynamoDBRequestRepository
from adapters.outbound.sns.sns_event_publisher import SNSEventPublisher
from adapters.outbound.sqs.sqs_message_dispatcher import SQSMessageDispatcher
from application.use_cases.get_request_status_use_case import GetRequestStatusUseCase
from application.use_cases.process_callback_use_case import ProcessCallbackUseCase
from application.use_cases.publish_outbox_use_case import PublishOutboxUseCase
from application.use_cases.reconcile_dispatches_use_case import ReconcileDispatchesUseCase
from application.use_cases.submit_request_use_case import SubmitRequestUseCase
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


def _create_boto3_resource(service_name: str, config: Settings) -> Any:
    kwargs: dict = {
        "region_name": config.aws_region,
        "aws_access_key_id": config.aws_access_key_id,
        "aws_secret_access_key": config.aws_secret_access_key,
    }
    if config.is_localstack_enabled:
        kwargs["endpoint_url"] = config.localstack_endpoint.strip()
    return boto3.resource(service_name, **kwargs)


def create_app(config: Settings = settings) -> FastAPI:
    """
    Composition Root:
    1. Loads config.
    2. Creates concrete AWS/LocalStack clients.
    3. Injects clients into Outbound Adapters.
    4. Injects Outbound Adapters into Application Use Cases.
    5. Sets up Inbound Adapters (FastAPI Router and Background Workers).
    """
    setup_logging(level=config.log_level)

    # 1. Concrete SDK Clients
    dynamodb_client = _create_boto3_client("dynamodb", config)
    dynamodb_resource = _create_boto3_resource("dynamodb", config)
    sqs_client = _create_boto3_client("sqs", config)
    sns_client = _create_boto3_client("sns", config)

    # 2. Outbound Adapters with injected clients
    request_repository = DynamoDBRequestRepository(
        dynamodb_resource=dynamodb_resource,
        table_name=config.dynamodb_requests_table,
    )
    outbox_repository = DynamoDBOutboxRepository(
        dynamodb_client=dynamodb_client,
        dynamodb_resource=dynamodb_resource,
        requests_table_name=config.dynamodb_requests_table,
        outbox_table_name=config.dynamodb_outbox_table,
    )
    message_dispatcher = SQSMessageDispatcher(
        sqs_client=sqs_client,
        queue_name=config.sqs_requests_queue_name,
        queue_url=config.sqs_requests_queue_url,
    )
    event_publisher = SNSEventPublisher(
        sns_client=sns_client,
        topic_arn=config.sns_topic_arn,
    )

    # 3. Application Use Cases
    submit_use_case = SubmitRequestUseCase(
        request_repository=request_repository,
        message_dispatcher=message_dispatcher,
    )
    callback_use_case = ProcessCallbackUseCase(
        request_repository=request_repository,
        outbox_repository=outbox_repository,
    )
    get_status_use_case = GetRequestStatusUseCase(
        request_repository=request_repository,
    )
    publish_outbox_use_case = PublishOutboxUseCase(
        outbox_repository=outbox_repository,
        event_publisher=event_publisher,
    )
    reconcile_use_case = ReconcileDispatchesUseCase(
        request_repository=request_repository,
        message_dispatcher=message_dispatcher,
        threshold_seconds=config.reconciler_pending_threshold_seconds,
    )

    # 4. Background Workers
    workers = BackgroundWorkers(
        publish_outbox_port=publish_outbox_use_case,
        reconcile_dispatches_port=reconcile_use_case,
        config=config,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting Share Grant Controller...")
        logger.info(
            f"LocalStack integration: {'ENABLED (' + config.localstack_endpoint + ')' if config.is_localstack_enabled else 'DISABLED (AWS)'}"
        )
        workers.start()
        yield
        logger.info("Stopping Share Grant Controller...")
        await workers.stop()

    def health_checker() -> dict:
        checks = {
            "status": "UP",
            "service": "share-grant-controller",
            "localstack_enabled": config.is_localstack_enabled,
        }
        try:
            dynamodb_client.describe_table(TableName=config.dynamodb_requests_table)
            checks["dynamodb"] = "OK"
        except Exception as e:
            checks["dynamodb"] = f"ERROR: {e}"
            checks["status"] = "DEGRADED"

        try:
            sqs_client.get_queue_url(QueueName=config.sqs_requests_queue_name)
            checks["sqs"] = "OK"
        except Exception as e:
            checks["sqs"] = f"ERROR: {e}"
            checks["status"] = "DEGRADED"

        return checks

    # 5. Inbound HTTP Adapter (FastAPI)
    app = FastAPI(
        title="Share & Grant Controller API",
        description="Hexagonal Architecture Controller for Databricks Unity Catalog permissions.",
        version="1.0.0",
        lifespan=lifespan,
    )

    router = create_router(
        submit_use_case=submit_use_case,
        callback_use_case=callback_use_case,
        get_status_use_case=get_status_use_case,
        health_checker=health_checker,
    )
    app.include_router(router)

    return app
