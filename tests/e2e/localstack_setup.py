"""
LocalStack resource provisioning for E2E tests.

Creates DynamoDB tables and S3 buckets matching the SAM template definitions.
"""

import boto3
from botocore.exceptions import ClientError


def _create_table_idempotent(dynamodb, **kwargs):
    """Create a table, ignoring ResourceInUseException (already exists)."""
    try:
        dynamodb.create_table(**kwargs)
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceInUseException':
            raise


def create_tables(endpoint_url: str) -> dict[str, str]:
    """Create all DynamoDB tables matching SAM template schemas.

    Returns:
        dict mapping logical name to table name.
    """
    dynamodb = boto3.client('dynamodb', endpoint_url=endpoint_url, region_name='us-east-1')

    tables = {}

    # Jobs table
    table_name = 'e2e-Jobs'
    _create_table_idempotent(dynamodb,
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'job_id', 'AttributeType': 'S'},
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'},
        ],
        KeySchema=[
            {'AttributeName': 'job_id', 'KeyType': 'HASH'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'user-id-index',
                'KeySchema': [
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    tables['jobs'] = table_name

    # Queue table
    table_name = 'e2e-Queue'
    _create_table_idempotent(dynamodb,
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'status', 'AttributeType': 'S'},
            {'AttributeName': 'job_id_timestamp', 'AttributeType': 'S'},
        ],
        KeySchema=[
            {'AttributeName': 'status', 'KeyType': 'HASH'},
            {'AttributeName': 'job_id_timestamp', 'KeyType': 'RANGE'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    tables['queue'] = table_name

    # Templates table
    table_name = 'e2e-Templates'
    _create_table_idempotent(dynamodb,
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'template_id', 'AttributeType': 'S'},
            {'AttributeName': 'version', 'AttributeType': 'N'},
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
        ],
        KeySchema=[
            {'AttributeName': 'template_id', 'KeyType': 'HASH'},
            {'AttributeName': 'version', 'KeyType': 'RANGE'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'user-id-index',
                'KeySchema': [
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    tables['templates'] = table_name

    # CostTracking table
    table_name = 'e2e-CostTracking'
    _create_table_idempotent(dynamodb,
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'job_id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
        ],
        KeySchema=[
            {'AttributeName': 'job_id', 'KeyType': 'HASH'},
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    tables['cost_tracking'] = table_name

    # Wait for all tables to be active
    for name in tables.values():
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=name, WaiterConfig={'Delay': 1, 'MaxAttempts': 30})

    return tables


def create_buckets(endpoint_url: str) -> str:
    """Create S3 data bucket.

    Returns:
        Bucket name.
    """
    s3 = boto3.client('s3', endpoint_url=endpoint_url, region_name='us-east-1')
    bucket_name = 'e2e-data-bucket'
    try:
        s3.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response['Error']['Code'] not in ('BucketAlreadyExists', 'BucketAlreadyOwnedByYou'):
            raise
    return bucket_name
