"""
CORS Integration Tests for Plot Palette API Gateway

Tests CORS configuration to ensure frontend (Amplify) can make cross-origin requests
to the API Gateway. Validates both preflight OPTIONS requests and actual requests.
"""

import os
import sys
import pytest
import requests
from typing import Dict


# API endpoint should be provided via environment variable or pytest fixture
@pytest.fixture
def api_endpoint():
    """Get API endpoint from environment variable"""
    endpoint = os.getenv('API_ENDPOINT')
    if not endpoint:
        pytest.skip("API_ENDPOINT environment variable not set")
    return endpoint


class TestCORSPreflight:
    """Test CORS preflight OPTIONS requests"""

    def test_health_endpoint_preflight(self, api_endpoint):
        """Test preflight request for /health endpoint"""
        response = requests.options(
            f"{api_endpoint}/health",
            headers={
                "Origin": "http://localhost:5173",  # Vite dev server
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type,Authorization"
            }
        )

        # Should return 200 or 204 for preflight
        assert response.status_code in [200, 204], f"Expected 200/204, got {response.status_code}"

        # Verify CORS headers
        headers = {k.lower(): v for k, v in response.headers.items()}

        assert "access-control-allow-origin" in headers, "Missing Access-Control-Allow-Origin header"
        assert headers["access-control-allow-origin"] == "*", \
            f"Expected wildcard origin, got {headers['access-control-allow-origin']}"

        assert "access-control-allow-methods" in headers, "Missing Access-Control-Allow-Methods header"
        allowed_methods = headers["access-control-allow-methods"].upper()
        assert "GET" in allowed_methods, "GET method not allowed"
        assert "POST" in allowed_methods, "POST method not allowed"
        assert "PUT" in allowed_methods, "PUT method not allowed"
        assert "DELETE" in allowed_methods, "DELETE method not allowed"
        assert "OPTIONS" in allowed_methods, "OPTIONS method not allowed"

        assert "access-control-allow-headers" in headers, "Missing Access-Control-Allow-Headers header"
        allowed_headers = headers["access-control-allow-headers"].lower()
        assert "content-type" in allowed_headers, "Content-Type header not allowed"
        assert "authorization" in allowed_headers, "Authorization header not allowed"

    def test_user_endpoint_preflight(self, api_endpoint):
        """Test preflight request for /user endpoint"""
        response = requests.options(
            f"{api_endpoint}/user",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )

        assert response.status_code in [200, 204], f"Expected 200/204, got {response.status_code}"

        headers = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers, "Missing Access-Control-Allow-Origin header"
        assert headers["access-control-allow-origin"] == "*"

    def test_preflight_with_amplify_origin(self, api_endpoint):
        """Test preflight with Amplify-like origin (for Phase 6)"""
        response = requests.options(
            f"{api_endpoint}/health",
            headers={
                "Origin": "https://main.d1234567890.amplifyapp.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        assert response.status_code in [200, 204]
        headers = {k.lower(): v for k, v in response.headers.items()}

        # With wildcard, any origin should be allowed
        assert "access-control-allow-origin" in headers


class TestCORSActualRequests:
    """Test actual requests with Origin header"""

    def test_health_with_origin(self, api_endpoint):
        """Test actual GET request to /health with Origin header"""
        response = requests.get(
            f"{api_endpoint}/health",
            headers={"Origin": "http://localhost:5173"}
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify CORS header in response
        headers = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers, \
            "Missing Access-Control-Allow-Origin in actual response"
        assert headers["access-control-allow-origin"] == "*", \
            f"Expected wildcard origin, got {headers['access-control-allow-origin']}"

        # Verify response body
        data = response.json()
        assert data["status"] == "healthy", "Health check returned unexpected status"

    def test_health_without_origin(self, api_endpoint):
        """Test request without Origin header (same-origin)"""
        response = requests.get(f"{api_endpoint}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_user_without_auth_with_origin(self, api_endpoint):
        """Test /user endpoint without auth token (should return 401)"""
        response = requests.get(
            f"{api_endpoint}/user",
            headers={"Origin": "http://localhost:5173"}
        )

        # Should return 401 because no auth token
        assert response.status_code == 401, \
            f"Expected 401 for unauthenticated request, got {response.status_code}"

        # CORS headers should still be present even on error
        headers = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers, \
            "CORS headers should be present even on 401 responses"

    def test_cors_with_multiple_origins(self, api_endpoint):
        """Test CORS with different origin values"""
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "https://example.com",
            "https://main.d1234567890.amplifyapp.com"
        ]

        for origin in origins:
            response = requests.get(
                f"{api_endpoint}/health",
                headers={"Origin": origin}
            )

            assert response.status_code == 200, f"Failed for origin: {origin}"
            headers = {k.lower(): v for k, v in response.headers.items()}
            assert "access-control-allow-origin" in headers, \
                f"CORS header missing for origin: {origin}"


class TestCORSHeaders:
    """Test specific CORS header configurations"""

    def test_max_age_header(self, api_endpoint):
        """Test Access-Control-Max-Age header in preflight"""
        response = requests.options(
            f"{api_endpoint}/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET"
            }
        )

        headers = {k.lower(): v for k, v in response.headers.items()}

        # Max-Age should be 300 seconds (5 minutes) as per api-stack.yaml
        if "access-control-max-age" in headers:
            max_age = int(headers["access-control-max-age"])
            assert max_age == 300, f"Expected max-age 300, got {max_age}"

    def test_allowed_headers_complete(self, api_endpoint):
        """Test that all required headers are in Allow-Headers"""
        response = requests.options(
            f"{api_endpoint}/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key"
            }
        )

        assert response.status_code in [200, 204]
        headers = {k.lower(): v for k, v in response.headers.items()}

        if "access-control-allow-headers" in headers:
            allowed = headers["access-control-allow-headers"].lower()
            required_headers = ["content-type", "authorization"]

            for required in required_headers:
                assert required in allowed, \
                    f"Required header '{required}' not in allowed headers: {allowed}"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring deployed infrastructure"
    )


if __name__ == "__main__":
    # Allow running directly for manual testing
    endpoint = os.getenv('API_ENDPOINT')
    if not endpoint:
        print("Error: API_ENDPOINT environment variable not set")
        print("Usage: API_ENDPOINT=https://xxx.execute-api.us-east-1.amazonaws.com python test_cors.py")
        sys.exit(1)

    print(f"Testing CORS for API endpoint: {endpoint}")
    pytest.main([__file__, "-v", "-s"])
