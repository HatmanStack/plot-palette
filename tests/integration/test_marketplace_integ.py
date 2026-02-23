"""
Integration tests for template marketplace — calls actual lambda_handlers against moto.

Tests search_templates and fork_template endpoints with real DynamoDB via moto.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.unit.handler_import import load_handler

_search_mod = load_handler("lambdas/templates/search_templates.py")
search_handler = _search_mod.lambda_handler

_fork_mod = load_handler("lambdas/templates/fork_template.py")
fork_handler = _fork_mod.lambda_handler


def _make_search_event(user_id="user-C", q=None, sort=None, limit=None):
    params = {}
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort
    if limit:
        params["limit"] = str(limit)
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "queryStringParameters": params or None,
        "body": None,
    }


def _make_fork_event(user_id="user-C", template_id="tmpl-pub-1", body=None):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-2",
        },
        "pathParameters": {"template_id": template_id},
        "queryStringParameters": None,
        "body": json.dumps(body) if body else None,
    }


def _create_templates_table(dynamodb):
    """Create Templates table with correct schema."""
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
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_templates(table):
    """Insert test templates: 2 public (user A), 1 private (user A), 1 public (user B)."""
    now = datetime.now(UTC)

    templates = [
        {
            "template_id": "tmpl-pub-1",
            "version": 1,
            "name": "Poetry Generator",
            "description": "Generates poetry datasets from author data",
            "user_id": "user-A",
            "is_public": True,
            "schema_requirements": ["author.name", "poem.text"],
            "template_definition": {
                "steps": [{"id": "q1", "prompt": "Write about {{ author.name }}"}]
            },
            "created_at": (now - timedelta(days=5)).isoformat(),
        },
        {
            "template_id": "tmpl-pub-2",
            "version": 1,
            "name": "Code Reviewer",
            "description": "Reviews code snippets and generates feedback",
            "user_id": "user-A",
            "is_public": True,
            "schema_requirements": ["code.snippet"],
            "template_definition": {
                "steps": [{"id": "review", "prompt": "Review {{ code.snippet }}"}]
            },
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "template_id": "tmpl-priv-1",
            "version": 1,
            "name": "Private Template",
            "description": "A private template",
            "user_id": "user-A",
            "is_public": False,
            "schema_requirements": ["data.field"],
            "template_definition": {
                "steps": [{"id": "gen", "prompt": "Generate {{ data.field }}"}]
            },
            "created_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "template_id": "tmpl-pub-3",
            "version": 1,
            "name": "Story Writer",
            "description": "Creates fictional stories",
            "user_id": "user-B",
            "is_public": True,
            "schema_requirements": ["character.name"],
            "template_definition": {
                "steps": [{"id": "story", "prompt": "Write about {{ character.name }}"}]
            },
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
    ]

    for t in templates:
        table.put_item(Item=t)


@mock_aws
def test_marketplace_returns_only_public():
    """Search as user C. Verify only 3 public templates returned."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _search_mod.templates_table = table

    result = search_handler(_make_search_event(user_id="user-C"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    assert body["count"] == 3
    template_ids = {t["template_id"] for t in body["templates"]}
    assert template_ids == {"tmpl-pub-1", "tmpl-pub-2", "tmpl-pub-3"}
    # Private template should NOT appear
    assert "tmpl-priv-1" not in template_ids


@mock_aws
def test_marketplace_search_with_query():
    """Search with query 'poetry'. Verify filtered results."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _search_mod.templates_table = table

    result = search_handler(_make_search_event(q="poetry"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    assert body["count"] == 1
    assert body["templates"][0]["template_id"] == "tmpl-pub-1"
    assert body["templates"][0]["name"] == "Poetry Generator"


@mock_aws
def test_fork_creates_independent_copy():
    """Fork a public template as user C. Verify new template in table with user C's user_id."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _fork_mod.templates_table = table

    with patch.object(_fork_mod, "generate_template_id", return_value="tmpl-forked"):
        result = fork_handler(_make_fork_event(user_id="user-C", template_id="tmpl-pub-1"), None)

    assert result["statusCode"] == 201
    body = json.loads(result["body"])
    assert body["template_id"] == "tmpl-forked"
    assert body["version"] == 1

    # Verify the forked template exists in the table
    response = table.get_item(Key={"template_id": "tmpl-forked", "version": 1})
    item = response["Item"]
    assert item["user_id"] == "user-C"
    assert item["is_public"] is False
    assert item["name"] == "Poetry Generator (fork)"
    assert item["template_definition"] == {
        "steps": [{"id": "q1", "prompt": "Write about {{ author.name }}"}]
    }
    assert item["schema_requirements"] == ["author.name", "poem.text"]


@mock_aws
def test_fork_private_template_denied():
    """Attempt to fork another user's private template. Verify 403."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _fork_mod.templates_table = table

    result = fork_handler(_make_fork_event(user_id="user-C", template_id="tmpl-priv-1"), None)

    assert result["statusCode"] == 403


@mock_aws
def test_search_omits_template_definition():
    """Verify template_definition is not in marketplace search results."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_templates_table(dynamodb)
    _insert_templates(table)

    _search_mod.templates_table = table

    result = search_handler(_make_search_event(), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    for tmpl in body["templates"]:
        assert "template_definition" not in tmpl
