#!/bin/bash
set -e

echo "=== Initializing LocalStack AWS Resources ==="

export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test}

LOCALSTACK_URL="http://localhost:4566"

# 1. Create SQS DLQ
echo "Creating SQS DLQ: share-grant-requests-dlq..."
DLQ_URL=$(aws --endpoint-url=$LOCALSTACK_URL sqs create-queue \
  --queue-name share-grant-requests-dlq \
  --output text --query 'QueueUrl')
echo "DLQ created: $DLQ_URL"

DLQ_ARN=$(aws --endpoint-url=$LOCALSTACK_URL sqs get-queue-attributes \
  --queue-url $DLQ_URL \
  --attribute-names QueueArn \
  --output text --query 'Attributes.QueueArn')
echo "DLQ ARN: $DLQ_ARN"

# 2. Create SQS Main Queue with Redrive Policy
echo "Creating SQS Main Queue: share-grant-requests-queue..."
REDRIVE_POLICY="{\"deadLetterTargetArn\":\"$DLQ_ARN\",\"maxReceiveCount\":\"3\"}"
MAIN_QUEUE_URL=$(aws --endpoint-url=$LOCALSTACK_URL sqs create-queue \
  --queue-name share-grant-requests-queue \
  --attributes "{\"RedrivePolicy\":$(echo $REDRIVE_POLICY | jq -R .)}" \
  --output text --query 'QueueUrl')
echo "Main SQS Queue created: $MAIN_QUEUE_URL"

# 3. Create SNS HUB Topic
echo "Creating SNS Topic: share-grant-hub-topic..."
SNS_TOPIC_ARN=$(aws --endpoint-url=$LOCALSTACK_URL sns create-topic \
  --name share-grant-hub-topic \
  --output text --query 'TopicArn')
echo "SNS Topic created: $SNS_TOPIC_ARN"

# 4. Create SQS queue for SNS topic subscription (to verify event delivery in tests)
echo "Creating SQS Queue for SNS subscriber: share-grant-sns-subscriber-queue..."
SNS_QUEUE_URL=$(aws --endpoint-url=$LOCALSTACK_URL sqs create-queue \
  --queue-name share-grant-sns-subscriber-queue \
  --output text --query 'QueueUrl')

SNS_QUEUE_ARN=$(aws --endpoint-url=$LOCALSTACK_URL sqs get-queue-attributes \
  --queue-url $SNS_QUEUE_URL \
  --attribute-names QueueArn \
  --output text --query 'Attributes.QueueArn')

# Subscribe SQS queue to SNS Topic
aws --endpoint-url=$LOCALSTACK_URL sns subscribe \
  --topic-arn $SNS_TOPIC_ARN \
  --protocol sqs \
  --notification-endpoint $SNS_QUEUE_ARN > /dev/null
echo "Subscribed test queue $SNS_QUEUE_ARN to SNS topic $SNS_TOPIC_ARN"

# 5. Create DynamoDB Table: share-grant-requests
echo "Creating DynamoDB Table: share-grant-requests..."
aws --endpoint-url=$LOCALSTACK_URL dynamodb create-table \
  --table-name share-grant-requests \
  --attribute-definitions \
      AttributeName=request_id,AttributeType=S \
      AttributeName=idempotency_key,AttributeType=S \
  --key-schema \
      AttributeName=request_id,KeyType=HASH \
  --global-secondary-indexes \
      "[{\"IndexName\":\"idempotency_key-index\",\"KeySchema\":[{\"AttributeName\":\"idempotency_key\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
  --billing-mode PAY_PER_REQUEST > /dev/null
echo "DynamoDB Table share-grant-requests created."

# 6. Create DynamoDB Table: share-grant-outbox
echo "Creating DynamoDB Table: share-grant-outbox..."
aws --endpoint-url=$LOCALSTACK_URL dynamodb create-table \
  --table-name share-grant-outbox \
  --attribute-definitions \
      AttributeName=event_id,AttributeType=S \
      AttributeName=status,AttributeType=S \
      AttributeName=created_at,AttributeType=S \
  --key-schema \
      AttributeName=event_id,KeyType=HASH \
  --global-secondary-indexes \
      "[{\"IndexName\":\"status-created_at-index\",\"KeySchema\":[{\"AttributeName\":\"status\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
  --billing-mode PAY_PER_REQUEST > /dev/null
echo "DynamoDB Table share-grant-outbox created."

echo "=== LocalStack AWS Resources initialized successfully! ==="
