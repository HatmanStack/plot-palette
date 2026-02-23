"""
Unit tests for seed data generation Lambda handler.
"""

import json
from unittest.mock import MagicMock

from tests.unit.handler_import import load_handler

_mod = load_handler("lambdas/seed_data/generate_seed_data.py")
lambda_handler = _mod.lambda_handler


def _make_event(body: dict, user_id: str = "user-123") -> dict:
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "http": {"method": "POST", "path": "/seed-data/generate"},
            "requestId": "req-001",
        },
        "body": json.dumps(body),
    }


def _base_body(**overrides) -> dict:
    body = {
        "template_id": "tmpl-123",
        "count": 10,
        "model_tier": "tier-1",
    }
    body.update(overrides)
    return body


def _mock_bedrock_response(text: str):
    """Create a mock Bedrock invoke_model response."""
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps({"generation": text}).encode()
    return {"body": mock_body}


class TestGenerateSeedData:
    def setup_method(self):
        self.mock_templates = MagicMock()
        self.mock_bedrock = MagicMock()
        self.mock_s3 = MagicMock()

        _mod.templates_table = self.mock_templates
        _mod.bedrock_client = self.mock_bedrock
        _mod.s3_client = self.mock_s3

        # Default: template exists with schema requirements (handler uses query first)
        self.mock_templates.query.return_value = {
            "Items": [
                {
                    "template_id": "tmpl-123",
                    "version": 1,
                    "name": "Test Template",
                    "user_id": "user-123",
                    "schema_requirements": ["author.name", "author.biography"],
                }
            ],
            "Count": 1,
        }

    def test_generate_success(self):
        """Mock Bedrock returning valid JSON array. Assert S3 upload called."""
        records = [
            {"author": {"name": "Jane Austen", "biography": "English novelist"}},
            {"author": {"name": "Mark Twain", "biography": "American writer"}},
        ]
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            json.dumps(records)
        )

        response = lambda_handler(_make_event(_base_body(count=2)), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["records_generated"] == 2
        assert body["records_invalid"] == 0
        assert "s3_key" in body
        self.mock_s3.put_object.assert_called_once()

    def test_generate_filters_invalid(self):
        """Mock Bedrock returning 4 records, 2 invalid. Assert filtering works."""
        records = [
            {"author": {"name": "Jane", "biography": "Writer"}},
            {"author": {"name": "Mark"}},  # Missing biography
            {"completely": "wrong"},  # Missing all fields
            {"author": {"name": "Emily", "biography": "Poet"}},
        ]
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            json.dumps(records)
        )

        response = lambda_handler(_make_event(_base_body(count=4)), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["records_generated"] == 2
        assert body["records_invalid"] == 2

    def test_generate_strips_markdown(self):
        """Mock Bedrock returning ```json\n[...]\n```. Assert parses correctly."""
        records = [{"author": {"name": "Jane", "biography": "Writer"}}]
        markdown_wrapped = f"```json\n{json.dumps(records)}\n```"
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            markdown_wrapped
        )

        response = lambda_handler(_make_event(_base_body(count=1)), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["records_generated"] == 1

    def test_generate_with_example(self):
        """Assert prompt includes example data."""
        records = [{"author": {"name": "Jane", "biography": "Writer"}}]
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            json.dumps(records)
        )

        body = _base_body(
            count=1,
            example_data={"author": {"name": "Emily", "biography": "Poet"}},
        )
        lambda_handler(_make_event(body), None)

        # Check that the prompt sent to Bedrock includes example
        call_args = self.mock_bedrock.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        prompt = request_body["prompt"]
        assert "Emily" in prompt

    def test_generate_with_instructions(self):
        """Assert prompt includes user instructions."""
        records = [{"author": {"name": "Jane", "biography": "Writer"}}]
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            json.dumps(records)
        )

        body = _base_body(count=1, instructions="Generate diverse authors")
        lambda_handler(_make_event(body), None)

        call_args = self.mock_bedrock.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        prompt = request_body["prompt"]
        assert "diverse authors" in prompt

    def test_generate_template_not_found(self):
        """Assert 404 when template doesn't exist."""
        self.mock_templates.query.return_value = {"Items": [], "Count": 0}
        self.mock_templates.get_item.return_value = {}

        response = lambda_handler(_make_event(_base_body()), None)
        assert response["statusCode"] == 404

    def test_generate_invalid_json_from_llm(self):
        """Mock Bedrock returning non-JSON. Assert 500 with error."""
        self.mock_bedrock.invoke_model.return_value = _mock_bedrock_response(
            "This is not valid JSON at all"
        )

        response = lambda_handler(_make_event(_base_body()), None)
        assert response["statusCode"] == 500
        assert "parse" in json.loads(response["body"])["error"].lower()

    def test_generate_max_count(self):
        """Request count=101 returns 400."""
        response = lambda_handler(_make_event(_base_body(count=101)), None)
        assert response["statusCode"] == 400
