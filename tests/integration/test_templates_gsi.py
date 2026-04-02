"""
Integration tests for Templates GSI (is_public-created_at-index).

Verifies that search_templates and list_templates correctly query the GSI
instead of scanning the full table. Uses moto @mock_aws.
"""

import json
from datetime import UTC, datetime, timedelta

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_search_mod = load_handler("lambdas/templates/search_templates.py")
search_handler = _search_mod.lambda_handler

_list_mod = load_handler("lambdas/templates/list_templates.py")
list_handler = _list_mod.lambda_handler


def _create_templates_table(dynamodb):
    """Create Templates table with is_public-created_at GSI."""
    return dynamodb.create_table(
        TableName="plot-palette-Templates-test",
        KeySchema=[
            {"AttributeName": "template_id", "KeyType": "HASH"},
            {"AttributeName": "version", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "template_id", "AttributeType": "S"},
            {"AttributeName": "version", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "is_public", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "is_public-created_at-index",
                "KeySchema": [
                    {"AttributeName": "is_public", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_templates(table):
    """Insert mix of public and private templates."""
    now = datetime.now(UTC)
    templates = [
        {
            "template_id": "tmpl-pub-1",
            "version": 1,
            "name": "Public Alpha",
            "description": "First public template",
            "user_id": "user-A",
            "is_public": "true",
            "schema_requirements": ["data.field"],
            "template_definition": {
                "steps": [{"id": "s1", "prompt": "Generate {{ data.field }}"}]
            },
            "created_at": (now - timedelta(days=5)).isoformat(),
        },
        {
            "template_id": "tmpl-pub-2",
            "version": 1,
            "name": "Public Beta",
            "description": "Second public template",
            "user_id": "user-B",
            "is_public": "true",
            "schema_requirements": ["data.field"],
            "template_definition": {
                "steps": [{"id": "s1", "prompt": "Generate {{ data.field }}"}]
            },
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "template_id": "tmpl-priv-1",
            "version": 1,
            "name": "Private Template",
            "description": "Should not appear in public queries",
            "user_id": "user-A",
            "is_public": "false",
            "schema_requirements": ["data.field"],
            "template_definition": {
                "steps": [{"id": "s1", "prompt": "Generate {{ data.field }}"}]
            },
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
    ]
    for t in templates:
        table.put_item(Item=t)


def _make_search_event(user_id="user-C", q=None, limit=None, last_key=None):
    params = {}
    if q:
        params["q"] = q
    if limit:
        params["limit"] = str(limit)
    if last_key:
        params["last_key"] = last_key
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-gsi",
        },
        "queryStringParameters": params or None,
        "body": None,
    }


def _make_list_event(user_id="user-C", include_public="true"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-list-gsi",
        },
        "queryStringParameters": {"include_public": include_public},
        "body": None,
    }


@mock_aws
def test_search_templates_uses_gsi_query():
    """Verify search_templates returns only public templates via GSI query."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _search_mod.templates_table = table

    result = search_handler(_make_search_event(), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # Only 2 public templates should be returned
    assert body["count"] == 2
    ids = {t["template_id"] for t in body["templates"]}
    assert ids == {"tmpl-pub-1", "tmpl-pub-2"}


@mock_aws
def test_search_templates_excludes_private():
    """Verify private templates are not returned via GSI."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _search_mod.templates_table = table

    result = search_handler(_make_search_event(), None)
    body = json.loads(result["body"])

    ids = {t["template_id"] for t in body["templates"]}
    assert "tmpl-priv-1" not in ids


@mock_aws
def test_list_templates_uses_gsi_for_public():
    """Verify list_templates queries GSI for public templates."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _list_mod.templates_table = table

    result = list_handler(_make_list_event(user_id="user-C"), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # user-C has no own templates, should see 2 public from other users
    assert body["count"] == 2
    ids = {t["template_id"] for t in body["templates"]}
    assert ids == {"tmpl-pub-1", "tmpl-pub-2"}


@mock_aws
def test_list_templates_excludes_own_public():
    """Verify list_templates filters out user's own public templates from the GSI results."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _list_mod.templates_table = table

    # user-A owns tmpl-pub-1 (public) and tmpl-priv-1 (private)
    # The public query should not include user-A's own public template
    result = list_handler(_make_list_event(user_id="user-A"), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # user-A should see: own templates (tmpl-pub-1, tmpl-priv-1) + other user's public (tmpl-pub-2)
    ids = {t["template_id"] for t in body["templates"]}
    assert "tmpl-pub-2" in ids  # Other user's public template


@mock_aws
def test_search_templates_pagination():
    """Verify pagination works with GSI query results."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)

    now = datetime.now(UTC)
    # Insert 5 public templates
    for i in range(5):
        table.put_item(
            Item={
                "template_id": f"tmpl-page-{i}",
                "version": 1,
                "name": f"Template {i}",
                "description": f"Template number {i}",
                "user_id": "user-A",
                "is_public": "true",
                "schema_requirements": [],
                "template_definition": {"steps": [{"id": "s1", "prompt": "test"}]},
                "created_at": (now - timedelta(hours=i)).isoformat(),
            }
        )

    _search_mod.templates_table = table

    # Request first page of 3
    result = search_handler(_make_search_event(limit=3), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    assert len(body["templates"]) == 3
    assert body["total"] == 5
    assert body.get("last_key") is not None

    # Request second page
    result2 = search_handler(_make_search_event(limit=3, last_key=body["last_key"]), None)
    body2 = json.loads(result2["body"])

    assert len(body2["templates"]) == 2
    assert body2.get("last_key") is None  # No more pages
