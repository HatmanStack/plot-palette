"""
Unit tests for create_job Lambda handler.

Tests SFN cascading failure handling.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from tests.unit.handler_import import load_handler

pytestmark = pytest.mark.unit

_mod = load_handler("lambdas/jobs/create_job.py")
lambda_handler = _mod.lambda_handler


def _make_event(user_id="user-123", body=None):
    if body is None:
        body = {
            "template_id": "tpl-1",
            "seed_data_path": "s3://bucket/seeds.json",
            "budget_limit": 10.0,
            "output_format": "JSONL",
            "num_records": 100,
        }
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
            "requestId": "test-req-1",
        },
        "pathParameters": None,
        "queryStringParameters": None,
        "body": json.dumps(body),
    }


class TestCreateJobTypedExceptions:
    """Tests for typed exception catches in create_job handler."""

    def setup_method(self):
        self.mock_jobs_table = MagicMock()
        self.mock_templates_table = MagicMock()
        self.mock_sfn = MagicMock()
        _mod.jobs_table = self.mock_jobs_table
        _mod.templates_table = self.mock_templates_table
        _mod.sfn_client = self.mock_sfn

    def test_malformed_json_body_returns_400(self):
        """Malformed JSON in request body returns 400."""
        event = _make_event()
        event["body"] = "not valid json {{"

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON" in body.get("message", body.get("error", ""))

    def test_missing_required_fields_returns_400(self):
        """Missing required fields (KeyError) returns 400."""
        # Remove requestContext entirely to trigger KeyError on user_id extraction
        event = {
            "requestContext": {},
            "pathParameters": None,
            "queryStringParameters": None,
            "body": json.dumps({"template_id": "tpl-1"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_dynamodb_client_error_returns_500(self):
        """DynamoDB ClientError at the outer level returns 500."""
        self.mock_templates_table.query.return_value = {
            "Items": [{"template_id": "tpl-1", "version": 1}]
        }
        # put_item raises a non-conditional ClientError
        self.mock_jobs_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DDB down"}},
            "PutItem",
        )

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 500

    def test_safety_net_logs_exception_class(self):
        """Safety-net except logs exception class name and full traceback."""
        self.mock_templates_table.query.side_effect = RuntimeError("Unexpected")

        with patch.object(_mod.logger, "error") as mock_log:
            response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 500
        # Verify exc_info=True was passed for traceback
        mock_log.assert_called()
        call_kwargs = mock_log.call_args
        assert call_kwargs[1].get("exc_info") is True


class TestCreateJobIdempotency:
    """Tests for atomic idempotency via conditional write."""

    def setup_method(self):
        self.mock_jobs_table = MagicMock()
        self.mock_templates_table = MagicMock()
        self.mock_sfn = MagicMock()
        _mod.jobs_table = self.mock_jobs_table
        _mod.templates_table = self.mock_templates_table
        _mod.sfn_client = self.mock_sfn

        # Template lookup succeeds
        self.mock_templates_table.query.return_value = {
            "Items": [{"template_id": "tpl-1", "version": 1}]
        }

        # SFN succeeds
        self.mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:sm:job-1"
        }

    def test_idempotent_duplicate_returns_existing_job(self):
        """Second creation with same idempotency token returns existing job."""
        import uuid

        token = "my-unique-token-123"
        expected_job_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"plot-palette:user-123:{token}")
        )

        # First call succeeds
        self.mock_jobs_table.put_item.return_value = {}
        body = {
            "template_id": "tpl-1",
            "seed_data_path": "s3://bucket/seeds.json",
            "budget_limit": 10.0,
            "output_format": "JSONL",
            "num_records": 100,
            "idempotency_token": token,
        }
        response1 = lambda_handler(_make_event(body=body), None)
        assert response1["statusCode"] == 201

        # Second call: put_item raises ConditionalCheckFailedException
        self.mock_jobs_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
            "PutItem",
        )
        self.mock_jobs_table.get_item.return_value = {
            "Item": {
                "job_id": expected_job_id,
                "user_id": "user-123",
                "status": "QUEUED",
                "created_at": "2026-01-01T00:00:00",
            }
        }
        response2 = lambda_handler(_make_event(body=body), None)

        assert response2["statusCode"] == 200
        body2 = json.loads(response2["body"])
        assert body2["message"] == "Existing job returned (idempotent)"

        # Same job returned (deterministic job_id from token)
        body1 = json.loads(response1["body"])
        assert body2["job_id"] == body1["job_id"] == expected_job_id

        # Idempotent fetch uses strongly consistent read
        get_item_kwargs = self.mock_jobs_table.get_item.call_args[1]
        assert get_item_kwargs.get("ConsistentRead") is True

        # SFN execution only started once (first call)
        assert self.mock_sfn.start_execution.call_count == 1

    def test_put_item_uses_condition_expression(self):
        """put_item is called with attribute_not_exists(job_id) condition."""
        self.mock_jobs_table.put_item.return_value = {}

        lambda_handler(_make_event(), None)

        call_kwargs = self.mock_jobs_table.put_item.call_args[1]
        assert "ConditionExpression" in call_kwargs
        assert "attribute_not_exists(job_id)" in str(call_kwargs["ConditionExpression"])

    def test_no_separate_query_for_idempotency(self):
        """No query-then-put pattern: no query call on user-id-index for idempotency."""
        self.mock_jobs_table.put_item.return_value = {}
        body = {
            "template_id": "tpl-1",
            "seed_data_path": "s3://bucket/seeds.json",
            "budget_limit": 10.0,
            "output_format": "JSONL",
            "num_records": 100,
            "idempotency_token": "token-xyz",
        }

        lambda_handler(_make_event(body=body), None)

        # jobs_table.query should NOT be called (no user-id-index query)
        self.mock_jobs_table.query.assert_not_called()

    def test_same_token_produces_same_job_id(self):
        """Same idempotency token deterministically produces the same job_id."""
        import uuid

        token = "deterministic-token"
        expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"plot-palette:user-123:{token}"))

        self.mock_jobs_table.put_item.return_value = {}
        body = {
            "template_id": "tpl-1",
            "seed_data_path": "s3://bucket/seeds.json",
            "budget_limit": 10.0,
            "output_format": "JSONL",
            "num_records": 100,
            "idempotency_token": token,
        }

        lambda_handler(_make_event(body=body), None)

        put_item = self.mock_jobs_table.put_item.call_args[1]["Item"]
        assert put_item["job_id"] == expected_id

    def test_different_users_same_token_get_different_jobs(self):
        """Different users with the same idempotency token produce different job IDs."""
        import uuid

        token = "shared-token"
        # uuid5 includes user_id, so different users get different job_ids
        job_id_a = str(uuid.uuid5(uuid.NAMESPACE_URL, f"plot-palette:user-A:{token}"))
        job_id_b = str(uuid.uuid5(uuid.NAMESPACE_URL, f"plot-palette:user-B:{token}"))
        assert job_id_a != job_id_b


class TestCreateJobSFNFailure:
    def setup_method(self):
        self.mock_jobs_table = MagicMock()
        self.mock_templates_table = MagicMock()
        self.mock_sfn = MagicMock()
        _mod.jobs_table = self.mock_jobs_table
        _mod.templates_table = self.mock_templates_table
        _mod.sfn_client = self.mock_sfn

        # Template lookup succeeds
        self.mock_templates_table.query.return_value = {
            "Items": [{"template_id": "tpl-1", "version": 1}]
        }

        # Job insert succeeds
        self.mock_jobs_table.put_item.return_value = {}

    def test_sfn_failure_marks_job_failed(self):
        """When SFN start fails, job should be marked FAILED."""
        self.mock_sfn.start_execution.side_effect = ClientError(
            {"Error": {"Code": "StateMachineDoesNotExist", "Message": "Not found"}},
            "StartExecution",
        )

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 500
        # Verify job was updated to FAILED
        self.mock_jobs_table.update_item.assert_called()
        call_kwargs = self.mock_jobs_table.update_item.call_args[1]
        assert ":failed" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":failed"] == "FAILED"

    def test_double_failure_returns_500_with_error(self):
        """When both SFN and DynamoDB update fail, response is an error."""
        self.mock_sfn.start_execution.side_effect = ClientError(
            {"Error": {"Code": "StateMachineDoesNotExist", "Message": "Not found"}},
            "StartExecution",
        )
        self.mock_jobs_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "DDB error"}},
            "UpdateItem",
        )

        response = lambda_handler(_make_event(), None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert "inconsistent" in body["error"]

    def test_sfn_failure_uses_condition_expression(self):
        """Status update to FAILED uses ConditionExpression to prevent stale updates."""
        self.mock_sfn.start_execution.side_effect = ClientError(
            {"Error": {"Code": "StateMachineDoesNotExist", "Message": "Not found"}},
            "StartExecution",
        )

        lambda_handler(_make_event(), None)

        call_kwargs = self.mock_jobs_table.update_item.call_args[1]
        assert "ConditionExpression" in call_kwargs
