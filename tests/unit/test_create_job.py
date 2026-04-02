"""
Unit tests for create_job Lambda handler.

Tests SFN cascading failure handling.
"""

import json
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from tests.unit.handler_import import load_handler

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

    def test_double_failure_returns_500_with_job_id(self):
        """When both SFN and DynamoDB update fail, response includes job_id."""
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
        # Response should include job_id for client recovery
        assert "job_id" in body

    def test_sfn_failure_uses_condition_expression(self):
        """Status update to FAILED uses ConditionExpression to prevent stale updates."""
        self.mock_sfn.start_execution.side_effect = ClientError(
            {"Error": {"Code": "StateMachineDoesNotExist", "Message": "Not found"}},
            "StartExecution",
        )

        lambda_handler(_make_event(), None)

        call_kwargs = self.mock_jobs_table.update_item.call_args[1]
        assert "ConditionExpression" in call_kwargs
