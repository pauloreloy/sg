#!/usr/bin/env python3
"""
Initializes LocalStack AWS resources (DynamoDB, SQS, SNS).
Works both inside LocalStack containers and on the host machine using boto3.
"""
import json
import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("boto3 is required to run this script. Please activate .venv or install boto3.")
    sys.exit(1)

LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"))
REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))

print(f"=== Initializing LocalStack AWS Resources at {LOCALSTACK_ENDPOINT} ===")

client_kwargs = {
    "region_name": REGION,
    "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
    "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    "endpoint_url": LOCALSTACK_ENDPOINT,
}

sqs = boto3.client("sqs", **client_kwargs)
sns = boto3.client("sns", **client_kwargs)
dynamodb = boto3.client("dynamodb", **client_kwargs)


def init_sqs():
    print("1. Creating SQS DLQ: share-grant-requests-dlq...")
    dlq_resp = sqs.create_queue(QueueName="share-grant-requests-dlq")
    dlq_url = dlq_resp["QueueUrl"]
    print(f"   DLQ created: {dlq_url}")

    dlq_attrs = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])
    dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
    print(f"   DLQ ARN: {dlq_arn}")

    print("2. Creating SQS Main Queue: share-grant-requests-queue...")
    redrive_policy = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})
    main_resp = sqs.create_queue(
        QueueName="share-grant-requests-queue",
        Attributes={"RedrivePolicy": redrive_policy},
    )
    print(f"   Main SQS Queue created: {main_resp['QueueUrl']}")
    return dlq_arn


def init_sns(dlq_arn):
    print("3. Creating SNS HUB Topic: share-grant-hub-topic...")
    topic_resp = sns.create_topic(Name="share-grant-hub-topic")
    topic_arn = topic_resp["TopicArn"]
    print(f"   SNS Topic created: {topic_arn}")

    print("4. Creating SQS Test Subscriber Queue: share-grant-sns-subscriber-queue...")
    test_q_resp = sqs.create_queue(QueueName="share-grant-sns-subscriber-queue")
    test_q_url = test_q_resp["QueueUrl"]
    test_q_attrs = sqs.get_queue_attributes(QueueUrl=test_q_url, AttributeNames=["QueueArn"])
    test_q_arn = test_q_attrs["Attributes"]["QueueArn"]

    # Subscribe queue to SNS topic
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=test_q_arn)
    print(f"   Subscribed {test_q_arn} to {topic_arn}")


def init_dynamodb():
    print("5. Creating DynamoDB Table: share-grant-requests...")
    try:
        dynamodb.create_table(
            TableName="share-grant-requests",
            AttributeDefinitions=[
                {"AttributeName": "request_id", "AttributeType": "S"},
                {"AttributeName": "idempotency_key", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "request_id", "KeyType": "HASH"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "idempotency_key-index",
                    "KeySchema": [
                        {"AttributeName": "idempotency_key", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("   Table share-grant-requests created.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print("   Table share-grant-requests already exists.")
        else:
            raise

    print("6. Creating DynamoDB Table: share-grant-outbox...")
    try:
        dynamodb.create_table(
            TableName="share-grant-outbox",
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "event_id", "KeyType": "HASH"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-created_at-index",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("   Table share-grant-outbox created.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print("   Table share-grant-outbox already exists.")
        else:
            raise


def main():
    try:
        dlq_arn = init_sqs()
        init_sns(dlq_arn)
        init_dynamodb()
        print("=== LocalStack AWS Resources initialized successfully! ===")
    except Exception as e:
        print(f"Error initializing LocalStack resources: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
