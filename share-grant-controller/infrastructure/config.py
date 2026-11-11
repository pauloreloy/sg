import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "test")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

    # LocalStack Endpoint: by default defined. If explicitly empty or unset, None is used.
    localstack_endpoint: Optional[str] = os.getenv(
        "LOCALSTACK_ENDPOINT",
        os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
    )

    # DynamoDB Tables
    dynamodb_requests_table: str = os.getenv("DYNAMODB_REQUESTS_TABLE", "share-grant-requests")
    dynamodb_outbox_table: str = os.getenv("DYNAMODB_OUTBOX_TABLE", "share-grant-outbox")

    # SQS Configuration
    sqs_requests_queue_name: str = os.getenv("SQS_REQUESTS_QUEUE_NAME", "share-grant-requests-queue")
    sqs_requests_queue_url: Optional[str] = os.getenv("SQS_REQUESTS_QUEUE_URL", None)
    sqs_dlq_name: str = os.getenv("SQS_DLQ_NAME", "share-grant-requests-dlq")

    # SNS Configuration
    sns_topic_arn: str = os.getenv(
        "SNS_TOPIC_ARN",
        "arn:aws:sns:us-east-1:000000000000:share-grant-hub-topic",
    )

    # Controller Service Configuration
    controller_host: str = os.getenv("CONTROLLER_HOST", "0.0.0.0")
    controller_port: int = int(os.getenv("CONTROLLER_PORT", "8000"))

    # Background Workers Configuration
    outbox_publisher_interval_seconds: float = float(os.getenv("OUTBOX_PUBLISHER_INTERVAL_SECONDS", "2.0"))
    reconciler_interval_seconds: float = float(os.getenv("RECONCILER_INTERVAL_SECONDS", "10.0"))
    reconciler_pending_threshold_seconds: int = int(os.getenv("RECONCILER_PENDING_THRESHOLD_SECONDS", "60"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def is_localstack_enabled(self) -> bool:
        return bool(self.localstack_endpoint and self.localstack_endpoint.strip())


settings = Settings()
