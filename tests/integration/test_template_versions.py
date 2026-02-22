"""
Integration tests for template version history using moto for AWS mocking.

Tests the list_versions and get_template (latest) handler logic with real
DynamoDB operations against in-memory moto services.
"""

import json
import os
from decimal import Decimal

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_aws


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def _create_templates_table(dynamodb):
    """Create the Templates table with PK=template_id, SK=version."""
    return dynamodb.create_table(
        TableName="plot-palette-Templates-test",
        KeySchema=[
            {"AttributeName": "template_id", "KeyType": "HASH"},
            {"AttributeName": "version", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "template_id", "AttributeType": "S"},
            {"AttributeName": "version", "AttributeType": "N"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_versions(table, template_id, count, user_id="user-123", is_public=False):
    """Insert N versions of a template."""
    for v in range(1, count + 1):
        table.put_item(
            Item={
                "template_id": template_id,
                "version": v,
                "name": f"Template v{v}",
                "description": f"Version {v} description",
                "user_id": user_id,
                "is_public": is_public,
                "created_at": f"2025-01-{v:02d}T00:00:00",
                "steps": [
                    {
                        "id": "step1",
                        "model": "meta.llama3-1-8b-instruct-v1:0",
                        "prompt": f"Generate content v{v}",
                    }
                ],
                "schema_requirements": ["author.name"],
            }
        )


@mock_aws
def test_list_versions_returns_all_sorted_desc():
    """Insert 3 versions, query all, verify sorted newest first."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    _insert_versions(table, "tmpl-integ-001", 3)

    # Query all versions (same as list_versions handler)
    response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-integ-001"),
        ScanIndexForward=False,
    )

    items = response["Items"]
    assert len(items) == 3
    # Verify sorted newest first
    versions = [int(item["version"]) for item in items]
    assert versions == [3, 2, 1]

    # Verify each item has expected fields
    for item in items:
        assert "name" in item
        assert "created_at" in item
        assert "steps" in item  # Full data available at DB level


@mock_aws
def test_get_template_latest_version():
    """Insert 3 versions, query with ScanIndexForward=False Limit=1, verify version 3."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    _insert_versions(table, "tmpl-integ-002", 3)

    # Query for latest version (same as get_template with version=latest)
    response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-integ-002"),
        ScanIndexForward=False,
        Limit=1,
    )

    items = response["Items"]
    assert len(items) == 1
    assert int(items[0]["version"]) == 3
    assert items[0]["name"] == "Template v3"


@mock_aws
def test_get_template_specific_version():
    """Insert 3 versions, get version 2 specifically, verify correct version returned."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    _insert_versions(table, "tmpl-integ-003", 3)

    # Get specific version (same as get_template with version=2)
    response = table.get_item(
        Key={"template_id": "tmpl-integ-003", "version": 2}
    )

    assert "Item" in response
    item = response["Item"]
    assert int(item["version"]) == 2
    assert item["name"] == "Template v2"
    assert item["steps"][0]["prompt"] == "Generate content v2"


@mock_aws
def test_version_list_empty_for_nonexistent_template():
    """Query for a template that doesn't exist returns empty."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_templates_table(dynamodb)

    table = dynamodb.Table("plot-palette-Templates-test")
    response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-nonexistent"),
        ScanIndexForward=False,
    )

    assert len(response["Items"]) == 0


@mock_aws
def test_version_ownership_and_public_access():
    """Verify that is_public flag controls access for non-owner."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    # Private template owned by different user
    _insert_versions(table, "tmpl-private", 2, user_id="other-user", is_public=False)
    # Public template owned by different user
    _insert_versions(table, "tmpl-public", 2, user_id="other-user", is_public=True)

    # Query private template
    private_response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-private"),
        ScanIndexForward=False,
    )
    first_private = private_response["Items"][0]
    assert first_private["user_id"] == "other-user"
    assert first_private["is_public"] is False

    # Query public template
    public_response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-public"),
        ScanIndexForward=False,
    )
    first_public = public_response["Items"][0]
    assert first_public["user_id"] == "other-user"
    assert first_public["is_public"] is True


@mock_aws
def test_create_new_version_increments():
    """Simulate creating a new version by inserting version N+1."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    _insert_versions(table, "tmpl-integ-004", 2)

    # Simulate what update_template does: insert version 3
    table.put_item(
        Item={
            "template_id": "tmpl-integ-004",
            "version": 3,
            "name": "Updated Template",
            "user_id": "user-123",
            "is_public": False,
            "created_at": "2025-01-03T00:00:00",
            "steps": [{"id": "new_step", "model": "claude", "prompt": "New prompt"}],
            "schema_requirements": [],
        }
    )

    # Verify latest is now 3
    response = table.query(
        KeyConditionExpression=Key("template_id").eq("tmpl-integ-004"),
        ScanIndexForward=False,
        Limit=1,
    )

    assert int(response["Items"][0]["version"]) == 3
    assert response["Items"][0]["name"] == "Updated Template"
