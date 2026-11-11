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

    # SQS Consumer Configuration
    sqs_requests_queue_name: str = os.getenv("SQS_REQUESTS_QUEUE_NAME", "share-grant-requests-queue")
    sqs_requests_queue_url: Optional[str] = os.getenv("SQS_REQUESTS_QUEUE_URL", None)
    sqs_poll_wait_time_seconds: int = int(os.getenv("SQS_POLL_WAIT_TIME_SECONDS", "5"))
    sqs_visibility_timeout_seconds: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT_SECONDS", "30"))

    # Databricks Configuration
    databricks_use_mock: bool = os.getenv("DATABRICKS_USE_MOCK", "true").lower() in ("true", "1", "yes")
    databricks_host: str = os.getenv("DATABRICKS_HOST", "https://dummy-workspace.cloud.databricks.com")
    databricks_client_id: str = os.getenv("DATABRICKS_CLIENT_ID", "dummy-client-id")
    databricks_client_secret: str = os.getenv("DATABRICKS_CLIENT_SECRET", "dummy-client-secret")
    databricks_max_retries: int = int(os.getenv("DATABRICKS_MAX_RETRIES", "3"))
    databricks_retry_backoff_seconds: float = float(os.getenv("DATABRICKS_RETRY_BACKOFF_SECONDS", "1.0"))

    # Controller Callback Configuration
    controller_url: str = os.getenv("CONTROLLER_URL", "http://localhost:8000")
    callback_max_retries: int = int(os.getenv("CALLBACK_MAX_RETRIES", "3"))
    callback_retry_backoff_seconds: float = float(os.getenv("CALLBACK_RETRY_BACKOFF_SECONDS", "1.0"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def is_localstack_enabled(self) -> bool:
        return bool(self.localstack_endpoint and self.localstack_endpoint.strip())


settings = Settings()
