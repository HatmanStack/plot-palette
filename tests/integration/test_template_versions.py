"""
Integration tests for template version history — calls actual lambda_handlers against moto.

Uses moto's @mock_aws to create real DynamoDB Templates table,
then invokes the actual list_versions and get_template lambda_handlers.
"""

import json
import os

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_list_mod = load_handler("lambdas/templates/list_versions.py")
_get_mod = load_handler("lambdas/templates/get_template.py")

list_versions_handler = _list_mod.lambda_handler
get_template_handler = _get_mod.lambda_handler


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


def _make_list_event(user_id="user-123", template_id="tmpl-integ-001"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"template_id": template_id},
    }


def _make_get_event(user_id="user-123", template_id="tmpl-integ-001", version=None):
    event = {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}}
        },
        "pathParameters": {"template_id": template_id},
        "queryStringParameters": {},
    }
    if version is not None:
        event["queryStringParameters"]["version"] = str(version)
    return event


@mock_aws
def test_list_versions_returns_all_sorted_desc():
    """Invoke actual list_versions handler: 3 versions -> sorted desc."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_versions(table, "tmpl-integ-001", 3)

    _list_mod.templates_table = table

    result = list_versions_handler(_make_list_event(), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["versions"]) == 3
    versions = [int(v["version"]) for v in body["versions"]]
    assert versions == [3, 2, 1]

    # Verify steps are NOT included (summary only)
    for v in body["versions"]:
        assert "steps" not in v
        assert "name" in v
        assert "created_at" in v


@mock_aws
def test_get_template_latest_version():
    """Invoke actual get_template handler with version=latest -> returns version 3."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_versions(table, "tmpl-integ-002", 3)

    _get_mod.templates_table = table

    result = get_template_handler(
        _make_get_event(template_id="tmpl-integ-002", version="latest"), None
    )

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert int(body["version"]) == 3
    assert body["name"] == "Template v3"


@mock_aws
def test_get_template_specific_version():
    """Invoke actual get_template handler with version=2 -> returns version 2."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_versions(table, "tmpl-integ-003", 3)

    _get_mod.templates_table = table

    result = get_template_handler(
        _make_get_event(template_id="tmpl-integ-003", version="2"), None
    )

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert int(body["version"]) == 2
    assert body["name"] == "Template v2"


@mock_aws
def test_version_list_empty_for_nonexistent_template():
    """Invoke actual list_versions handler: nonexistent template -> 404."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_templates_table(dynamodb)

    _list_mod.templates_table = dynamodb.Table("plot-palette-Templates-test")

    result = list_versions_handler(
        _make_list_event(template_id="tmpl-nonexistent"), None
    )

    assert result["statusCode"] == 404


@mock_aws
def test_version_ownership_and_public_access():
    """Invoke actual list_versions handler: private -> 403, public -> 200."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    _insert_versions(table, "tmpl-private", 2, user_id="other-user", is_public=False)
    _insert_versions(table, "tmpl-public", 2, user_id="other-user", is_public=True)

    _list_mod.templates_table = table

    # Private template owned by different user -> 403
    private_result = list_versions_handler(
        _make_list_event(template_id="tmpl-private"), None
    )
    assert private_result["statusCode"] == 403

    # Public template owned by different user -> 200
    public_result = list_versions_handler(
        _make_list_event(template_id="tmpl-public"), None
    )
    assert public_result["statusCode"] == 200


@mock_aws
def test_create_new_version_increments():
    """Verify latest query returns version 3 after inserting it."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_versions(table, "tmpl-integ-004", 2)

    # Insert version 3
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

    _get_mod.templates_table = table

    result = get_template_handler(
        _make_get_event(template_id="tmpl-integ-004", version="latest"), None
    )

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert int(body["version"]) == 3
    assert body["name"] == "Updated Template"
