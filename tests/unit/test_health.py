"""
Unit tests for health check Lambda function

Tests the /health endpoint Lambda handler without requiring deployed infrastructure.
"""

import json
import pytest
from datetime import datetime


# Mock Lambda context
class MockContext:
    def __init__(self):
        self.request_id = "test-request-id-12345"
        self.function_name = "plot-palette-health-test"
        self.memory_limit_in_mb = 128
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"


# Health check handler code (same as in api-stack.yaml)
def lambda_handler(event, context):
    """Health check endpoint - returns API status"""
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    logger.info(json.dumps({
        "event": "health_check",
        "request_id": context.request_id
    }))

    response = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "plot-palette-api"
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response)
    }


class TestHealthCheckHandler:
    """Test health check Lambda handler"""

    def test_health_check_returns_200(self):
        """Test that handler returns 200 status code"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200, \
            f"Expected status code 200, got {response['statusCode']}"

    def test_health_check_returns_json(self):
        """Test that handler returns JSON content type"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)

        assert "headers" in response, "Response missing headers"
        assert response["headers"]["Content-Type"] == "application/json", \
            "Content-Type should be application/json"

    def test_health_check_includes_cors_header(self):
        """Test that handler includes CORS header"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)

        assert "Access-Control-Allow-Origin" in response["headers"], \
            "Missing CORS header"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*", \
            "CORS header should allow all origins"

    def test_health_check_body_format(self):
        """Test that response body has correct format"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)

        assert "body" in response, "Response missing body"

        body = json.loads(response["body"])

        assert "status" in body, "Body missing status field"
        assert body["status"] == "healthy", \
            f"Expected status 'healthy', got '{body['status']}'"

        assert "timestamp" in body, "Body missing timestamp field"
        assert "version" in body, "Body missing version field"
        assert body["version"] == "1.0.0", \
            f"Expected version '1.0.0', got '{body['version']}'"

        assert "service" in body, "Body missing service field"
        assert body["service"] == "plot-palette-api", \
            f"Expected service 'plot-palette-api', got '{body['service']}'"

    def test_health_check_timestamp_valid(self):
        """Test that timestamp is valid ISO format"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        # Try to parse timestamp - will raise exception if invalid
        timestamp_str = body["timestamp"]
        try:
            datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp_str}")

    def test_health_check_with_api_gateway_event(self):
        """Test with realistic API Gateway event structure"""
        event = {
            "version": "2.0",
            "routeKey": "GET /health",
            "rawPath": "/health",
            "headers": {
                "accept": "*/*",
                "user-agent": "curl/7.68.0"
            },
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "abcd1234",
                "domainName": "abcd1234.execute-api.us-east-1.amazonaws.com",
                "http": {
                    "method": "GET",
                    "path": "/health"
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "healthy"

    def test_health_check_idempotent(self):
        """Test that multiple calls return consistent results"""
        event = {}
        context = MockContext()

        # Call handler multiple times
        responses = [lambda_handler(event, context) for _ in range(5)]

        # All should return 200
        for response in responses:
            assert response["statusCode"] == 200

            body = json.loads(response["body"])
            assert body["status"] == "healthy"
            assert body["version"] == "1.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
