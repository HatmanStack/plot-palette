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
