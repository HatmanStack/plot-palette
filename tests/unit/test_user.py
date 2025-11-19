"""
Unit tests for user info Lambda function

Tests the /user endpoint Lambda handler without requiring deployed infrastructure.
"""

import json
import pytest


# Mock Lambda context
class MockContext:
    def __init__(self):
        self.request_id = "test-request-id-67890"
        self.function_name = "plot-palette-user-test"
        self.memory_limit_in_mb = 128


# User info handler code (same as in api-stack.yaml)
def lambda_handler(event, context):
    """Get current user information from JWT claims"""
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    logger.info(json.dumps({
        "event": "get_user_info",
        "request_id": context.request_id
    }))

    try:
        # Extract claims from JWT (set by API Gateway authorizer)
        claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})

        if not claims:
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Unauthorized"})
            }

        user_info = {
            "user_id": claims.get('sub'),
            "email": claims.get('email'),
            "email_verified": claims.get('email_verified'),
            "name": claims.get('name'),
            "role": claims.get('custom:user_role', 'user'),
            "token_issued_at": claims.get('iat'),
            "token_expires_at": claims.get('exp')
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(user_info)
        }

    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"})
        }


class TestUserInfoHandler:
    """Test user info Lambda handler"""

    def test_user_info_success(self):
        """Test successful user info retrieval"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "user-123-456",
                            "email": "test@example.com",
                            "email_verified": "true",
                            "name": "Test User",
                            "custom:user_role": "admin",
                            "iat": "1700000000",
                            "exp": "1700003600"
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200, \
            f"Expected status code 200, got {response['statusCode']}"

        body = json.loads(response["body"])

        assert body["user_id"] == "user-123-456"
        assert body["email"] == "test@example.com"
        assert body["email_verified"] == "true"
        assert body["name"] == "Test User"
        assert body["role"] == "admin"
        assert body["token_issued_at"] == "1700000000"
        assert body["token_expires_at"] == "1700003600"

    def test_user_info_unauthorized_no_claims(self):
        """Test that missing claims return 401"""
        event = {}
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 401, \
            f"Expected status code 401, got {response['statusCode']}"

        body = json.loads(response["body"])
        assert "error" in body
        assert body["error"] == "Unauthorized"

    def test_user_info_unauthorized_empty_claims(self):
        """Test that empty claims return 401"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {}
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 401

    def test_user_info_default_role(self):
        """Test that role defaults to 'user' if not provided"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "user-789",
                            "email": "user@example.com"
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        assert body["role"] == "user", \
            "Default role should be 'user'"

    def test_user_info_includes_cors_header(self):
        """Test that response includes CORS header"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "user-123",
                            "email": "test@example.com"
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert "headers" in response
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_user_info_handles_missing_optional_fields(self):
        """Test that optional fields can be missing"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "user-minimal",
                            "email": "minimal@example.com"
                            # Missing: name, email_verified, role, iat, exp
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        assert body["user_id"] == "user-minimal"
        assert body["email"] == "minimal@example.com"
        assert body["name"] is None
        assert body["email_verified"] is None
        assert body["role"] == "user"  # Default

    def test_user_info_with_api_gateway_event_structure(self):
        """Test with realistic API Gateway event structure"""
        event = {
            "version": "2.0",
            "routeKey": "GET /user",
            "headers": {
                "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            },
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "abcd1234",
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "cognito-user-123",
                            "email": "apigateway@example.com",
                            "email_verified": "true",
                            "cognito:username": "apigateway@example.com"
                        },
                        "scopes": ["email", "openid", "profile"]
                    }
                },
                "http": {
                    "method": "GET",
                    "path": "/user"
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user_id"] == "cognito-user-123"
        assert body["email"] == "apigateway@example.com"

    def test_user_info_custom_role_admin(self):
        """Test custom role extraction (admin)"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "admin-user",
                            "email": "admin@example.com",
                            "custom:user_role": "admin"
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        body = json.loads(response["body"])
        assert body["role"] == "admin"

    def test_user_info_multiple_custom_attributes(self):
        """Test extraction of multiple custom attributes"""
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "org-user",
                            "email": "user@org.com",
                            "custom:user_role": "user",
                            "custom:organization": "Acme Corp"
                        }
                    }
                }
            }
        }
        context = MockContext()

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["role"] == "user"
        # Note: organization not extracted in current implementation
        # Could be added if needed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
