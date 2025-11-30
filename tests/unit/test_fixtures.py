"""
Tests to verify test fixtures work correctly.

This file tests the fixture factories and utilities to ensure
they produce valid test data.
"""

import pytest
from datetime import datetime


class TestFixtureFactories:
    """Test fixture factory functions."""

    def test_lambda_event_v2_default(self):
        """Test default API Gateway v2 event."""
        from tests.fixtures import make_api_gateway_event_v2

        event = make_api_gateway_event_v2()

        assert event["version"] == "2.0"
        assert event["rawPath"] == "/"
        assert "requestContext" in event
        assert "authorizer" in event["requestContext"]
        assert "jwt" in event["requestContext"]["authorizer"]
        assert "claims" in event["requestContext"]["authorizer"]["jwt"]

    def test_lambda_event_v2_with_body(self):
        """Test API Gateway v2 event with body."""
        from tests.fixtures import make_api_gateway_event_v2

        event = make_api_gateway_event_v2(
            method="POST",
            path="/jobs",
            body={"template-id": "abc123", "budget-limit": 100},
        )

        assert event["requestContext"]["http"]["method"] == "POST"
        assert event["body"] is not None
        import json
        body = json.loads(event["body"])
        assert body["template-id"] == "abc123"

    def test_lambda_event_v2_with_user_id(self):
        """Test API Gateway v2 event with custom user ID."""
        from tests.fixtures import make_api_gateway_event_v2

        event = make_api_gateway_event_v2(user_id="custom-user-456")

        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        assert claims["sub"] == "custom-user-456"

    def test_lambda_event_v2_with_path_params(self):
        """Test API Gateway v2 event with path parameters."""
        from tests.fixtures import make_api_gateway_event_v2

        event = make_api_gateway_event_v2(
            method="GET",
            path="/jobs/{jobId}",
            path_parameters={"jobId": "job-123"},
        )

        assert event["pathParameters"]["jobId"] == "job-123"

    def test_job_item_factory(self):
        """Test DynamoDB job item factory."""
        from tests.fixtures import make_job_item

        item = make_job_item(
            job_id="test-123",
            user_id="user-456",
            status="RUNNING",
            budget_limit=50.0,
        )

        assert item["job_id"]["S"] == "test-123"
        assert item["user_id"]["S"] == "user-456"
        assert item["status"]["S"] == "RUNNING"
        assert item["budget_limit"]["N"] == "50.0"

    def test_template_item_factory(self):
        """Test DynamoDB template item factory."""
        from tests.fixtures import make_template_item

        item = make_template_item(
            template_id="template-abc",
            name="My Template",
            is_public=True,
        )

        assert item["template_id"]["S"] == "template-abc"
        assert item["name"]["S"] == "My Template"
        assert item["is_public"]["BOOL"] is True
        assert "steps" in item

    def test_queue_item_factory(self):
        """Test DynamoDB queue item factory."""
        from tests.fixtures import make_queue_item

        item = make_queue_item(
            job_id="job-123",
            status="RUNNING",
            task_arn="arn:aws:ecs:test",
        )

        assert item["status"]["S"] == "RUNNING"
        assert item["job_id"]["S"] == "job-123"
        assert item["task_arn"]["S"] == "arn:aws:ecs:test"
        assert "job_id_timestamp" in item

    def test_checkpoint_item_factory(self):
        """Test checkpoint state factory."""
        from tests.fixtures import make_checkpoint_item

        checkpoint = make_checkpoint_item(
            job_id="job-123",
            records_generated=1000,
            tokens_used=200000,
        )

        assert checkpoint["job_id"] == "job-123"
        assert checkpoint["records_generated"] == 1000
        assert checkpoint["tokens_used"] == 200000
        assert "resume_state" in checkpoint


class TestPytestFixtures:
    """Test pytest fixtures from conftest files."""

    def test_sample_job_config(self, sample_job_config):
        """Test sample_job_config fixture."""
        assert "job_id" in sample_job_config
        assert "user_id" in sample_job_config
        assert "status" in sample_job_config
        assert "budget_limit" in sample_job_config
        assert sample_job_config["budget_limit"] == 100.0

    def test_sample_template(self, sample_template):
        """Test sample_template fixture."""
        assert "template_id" in sample_template
        assert "steps" in sample_template
        assert len(sample_template["steps"]) == 2
        assert sample_template["steps"][0]["id"] == "question"

    def test_sample_checkpoint(self, sample_checkpoint):
        """Test sample_checkpoint fixture."""
        assert "job_id" in sample_checkpoint
        assert "records_generated" in sample_checkpoint
        assert sample_checkpoint["records_generated"] == 500

    def test_sample_seed_data(self, sample_seed_data):
        """Test sample_seed_data fixture."""
        assert "author" in sample_seed_data
        assert "poem" in sample_seed_data
        assert sample_seed_data["author"]["name"] == "Emily Dickinson"


class TestMockClients:
    """Test mock AWS client fixtures."""

    def test_mock_dynamodb_client(self, mock_dynamodb_client):
        """Test mock DynamoDB client."""
        # Verify the mock is callable
        result = mock_dynamodb_client.get_item(
            TableName="test",
            Key={"pk": {"S": "test"}}
        )
        assert result == {"Item": None}

    def test_mock_s3_client(self, mock_s3_client):
        """Test mock S3 client."""
        result = mock_s3_client.get_object(
            Bucket="test",
            Key="test.json"
        )
        assert "Body" in result
        assert "ETag" in result

    def test_mock_bedrock_client(self, mock_bedrock_client):
        """Test mock Bedrock client."""
        import json

        # Test Claude model
        result = mock_bedrock_client.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({"messages": [{"role": "user", "content": "test"}]})
        )
        response = json.loads(result["body"].read())
        assert "content" in response

        # Test Llama model
        result = mock_bedrock_client.invoke_model(
            modelId="meta.llama3-1-8b-instruct-v1:0",
            body=json.dumps({"prompt": "test"})
        )
        response = json.loads(result["body"].read())
        assert "generation" in response

    def test_mock_ecs_client(self, mock_ecs_client):
        """Test mock ECS client."""
        result = mock_ecs_client.run_task(
            cluster="test",
            taskDefinition="test",
        )
        assert "tasks" in result
        assert len(result["tasks"]) == 1
        assert "taskArn" in result["tasks"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
