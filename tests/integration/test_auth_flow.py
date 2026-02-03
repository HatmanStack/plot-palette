"""
End-to-End Authentication Flow Tests for Plot Palette

Tests the complete authentication flow from user signup through accessing
protected API endpoints. Validates Cognito User Pool and API Gateway JWT
authorization integration.

These tests require REAL AWS Cognito credentials and are skipped by default.
To run: REAL_AUTH_TESTS=1 pytest tests/integration/test_auth_flow.py
"""

import os
import sys
import time
import pytest
import boto3
import requests
from datetime import datetime
from botocore.exceptions import ClientError

# Skip entire module unless REAL_AUTH_TESTS is set
if not os.getenv('REAL_AUTH_TESTS'):
    pytest.skip(
        "Skipping auth flow tests (require real AWS Cognito). "
        "Set REAL_AUTH_TESTS=1 to run.",
        allow_module_level=True
    )


@pytest.fixture(scope="class")
def cognito_client():
    """Create Cognito IDP client"""
    return boto3.client('cognito-idp')


@pytest.fixture(scope="class")
def user_pool_id():
    """Get User Pool ID from environment"""
    pool_id = os.getenv('USER_POOL_ID')
    if not pool_id:
        pytest.skip("USER_POOL_ID environment variable not set")
    return pool_id


@pytest.fixture(scope="class")
def client_id():
    """Get User Pool Client ID from environment"""
    cid = os.getenv('CLIENT_ID')
    if not cid:
        pytest.skip("CLIENT_ID environment variable not set")
    return cid


@pytest.fixture(scope="class")
def api_endpoint():
    """Get API endpoint from environment"""
    endpoint = os.getenv('API_ENDPOINT')
    if not endpoint:
        pytest.skip("API_ENDPOINT environment variable not set")
    return endpoint


@pytest.fixture(scope="class")
def test_user_email():
    """Generate unique test user email"""
    timestamp = int(datetime.now().timestamp() * 1000)
    return f"test+{timestamp}@example.com"


@pytest.fixture(scope="class")
def test_password():
    """Test user password (meets complexity requirements)"""
    return "TestPassword123!@#"


class TestAuthenticationFlow:
    """
    Test complete authentication flow with ordered test execution.
    Tests run in sequence and share state via class attributes.
    """

    # Class-level state shared across tests
    user_sub = None
    id_token = None
    access_token = None
    refresh_token = None
    new_id_token = None

    def test_01_signup_new_user(
        self,
        cognito_client,
        client_id,
        test_user_email,
        test_password
    ):
        """Test user signup with Cognito"""
        print(f"\n[Test 1] Signing up user: {test_user_email}")

        response = cognito_client.sign_up(
            ClientId=client_id,
            Username=test_user_email,
            Password=test_password,
            UserAttributes=[
                {'Name': 'email', 'Value': test_user_email},
                {'Name': 'name', 'Value': 'Test User'}
            ]
        )

        # Store user sub for later use
        TestAuthenticationFlow.user_sub = response['UserSub']

        assert 'UserSub' in response, "Signup response missing UserSub"
        assert response['UserConfirmed'] is False, "User should not be confirmed yet"

        print(f"✓ User signed up successfully. UserSub: {TestAuthenticationFlow.user_sub}")

    def test_02_signup_duplicate_user(
        self,
        cognito_client,
        client_id,
        test_user_email,
        test_password
    ):
        """Test that duplicate signup fails"""
        print(f"\n[Test 2] Testing duplicate signup for: {test_user_email}")

        with pytest.raises(ClientError) as exc_info:
            cognito_client.sign_up(
                ClientId=client_id,
                Username=test_user_email,
                Password=test_password,
                UserAttributes=[
                    {'Name': 'email', 'Value': test_user_email}
                ]
            )

        error_code = exc_info.value.response['Error']['Code']
        assert error_code == 'UsernameExistsException', \
            f"Expected UsernameExistsException, got {error_code}"

        print("✓ Duplicate signup correctly rejected")

    def test_03_login_unconfirmed_user(
        self,
        cognito_client,
        client_id,
        test_user_email,
        test_password
    ):
        """Test that unconfirmed user cannot login"""
        print(f"\n[Test 3] Testing login for unconfirmed user")

        with pytest.raises(ClientError) as exc_info:
            cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': test_user_email,
                    'PASSWORD': test_password
                }
            )

        error_code = exc_info.value.response['Error']['Code']
        assert error_code == 'UserNotConfirmedException', \
            f"Expected UserNotConfirmedException, got {error_code}"

        print("✓ Unconfirmed user correctly rejected")

    def test_04_confirm_user(
        self,
        cognito_client,
        user_pool_id,
        test_user_email
    ):
        """Admin confirm user (simulates email verification)"""
        print(f"\n[Test 4] Confirming user via admin")

        cognito_client.admin_confirm_sign_up(
            UserPoolId=user_pool_id,
            Username=test_user_email
        )

        # Verify user is confirmed
        user = cognito_client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=test_user_email
        )

        assert user['UserStatus'] == 'CONFIRMED', \
            f"Expected CONFIRMED status, got {user['UserStatus']}"

        print("✓ User confirmed successfully")

    def test_05_login_with_valid_credentials(
        self,
        cognito_client,
        client_id,
        test_user_email,
        test_password
    ):
        """Test login with valid credentials and retrieve tokens"""
        print(f"\n[Test 5] Logging in with valid credentials")

        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': test_user_email,
                'PASSWORD': test_password
            }
        )

        assert 'AuthenticationResult' in response, "Login response missing AuthenticationResult"

        # Store tokens for later tests
        auth_result = response['AuthenticationResult']
        TestAuthenticationFlow.id_token = auth_result['IdToken']
        TestAuthenticationFlow.access_token = auth_result['AccessToken']
        TestAuthenticationFlow.refresh_token = auth_result['RefreshToken']

        assert TestAuthenticationFlow.id_token is not None, "Missing ID token"
        assert TestAuthenticationFlow.access_token is not None, "Missing access token"
        assert TestAuthenticationFlow.refresh_token is not None, "Missing refresh token"

        # Verify token expiration times
        assert 'ExpiresIn' in auth_result, "Missing token expiration info"
        assert auth_result['ExpiresIn'] == 3600, \
            f"Expected 3600s (60min) expiration, got {auth_result['ExpiresIn']}"

        print(f"✓ Login successful. Tokens retrieved.")
        print(f"  - ID Token: {TestAuthenticationFlow.id_token[:50]}...")
        print(f"  - Access Token: {TestAuthenticationFlow.access_token[:50]}...")
        print(f"  - Refresh Token: {TestAuthenticationFlow.refresh_token[:50]}...")

    def test_06_login_with_wrong_password(
        self,
        cognito_client,
        client_id,
        test_user_email
    ):
        """Test login with incorrect password"""
        print(f"\n[Test 6] Testing login with wrong password")

        with pytest.raises(ClientError) as exc_info:
            cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': test_user_email,
                    'PASSWORD': 'WrongPassword123!'
                }
            )

        error_code = exc_info.value.response['Error']['Code']
        assert error_code == 'NotAuthorizedException', \
            f"Expected NotAuthorizedException, got {error_code}"

        print("✓ Wrong password correctly rejected")

    def test_07_access_protected_endpoint_without_token(self, api_endpoint):
        """Test accessing /user endpoint without auth token"""
        print(f"\n[Test 7] Testing /user endpoint without token")

        response = requests.get(f"{api_endpoint}/user")

        assert response.status_code == 401, \
            f"Expected 401 Unauthorized, got {response.status_code}"

        print("✓ Unauthenticated request correctly rejected with 401")

    def test_08_access_protected_endpoint_with_invalid_token(self, api_endpoint):
        """Test accessing /user endpoint with malformed token"""
        print(f"\n[Test 8] Testing /user endpoint with invalid token")

        response = requests.get(
            f"{api_endpoint}/user",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401, \
            f"Expected 401 for invalid token, got {response.status_code}"

        print("✓ Invalid token correctly rejected with 401")

    def test_09_access_protected_endpoint_with_valid_token(
        self,
        api_endpoint,
        test_user_email
    ):
        """Test accessing /user endpoint with valid JWT token"""
        print(f"\n[Test 9] Testing /user endpoint with valid token")

        assert TestAuthenticationFlow.id_token is not None, \
            "ID token not available (test_05 must run first)"

        response = requests.get(
            f"{api_endpoint}/user",
            headers={"Authorization": f"Bearer {TestAuthenticationFlow.id_token}"}
        )

        assert response.status_code == 200, \
            f"Expected 200 OK, got {response.status_code}"

        # Verify user data in response
        user_data = response.json()

        assert 'user_id' in user_data, "Response missing user_id"
        assert 'email' in user_data, "Response missing email"
        assert user_data['email'] == test_user_email, \
            f"Expected email {test_user_email}, got {user_data['email']}"
        assert user_data['user_id'] == TestAuthenticationFlow.user_sub, \
            f"User ID mismatch"

        print(f"✓ Protected endpoint accessible with valid token")
        print(f"  User data: {user_data}")

    def test_10_access_public_endpoint_without_token(self, api_endpoint):
        """Test accessing /health endpoint without token (should work)"""
        print(f"\n[Test 10] Testing /health endpoint without token")

        response = requests.get(f"{api_endpoint}/health")

        assert response.status_code == 200, \
            f"Expected 200 OK for health check, got {response.status_code}"

        data = response.json()
        assert data['status'] == 'healthy', \
            f"Expected healthy status, got {data.get('status')}"

        print("✓ Public health endpoint accessible without token")

    def test_11_refresh_token_flow(
        self,
        cognito_client,
        client_id
    ):
        """Test refreshing tokens using refresh token"""
        print(f"\n[Test 11] Testing token refresh")

        assert TestAuthenticationFlow.refresh_token is not None, \
            "Refresh token not available (test_05 must run first)"

        # Wait a moment to ensure new tokens are different
        time.sleep(1)

        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': TestAuthenticationFlow.refresh_token
            }
        )

        assert 'AuthenticationResult' in response, "Refresh response missing AuthenticationResult"

        auth_result = response['AuthenticationResult']
        TestAuthenticationFlow.new_id_token = auth_result['IdToken']
        new_access_token = auth_result['AccessToken']

        assert TestAuthenticationFlow.new_id_token is not None, "Missing new ID token"
        assert new_access_token is not None, "Missing new access token"

        # New tokens should be different from old tokens
        assert TestAuthenticationFlow.new_id_token != TestAuthenticationFlow.id_token, \
            "New ID token should be different from old token"

        print("✓ Token refresh successful")
        print(f"  New ID Token: {TestAuthenticationFlow.new_id_token[:50]}...")

    def test_12_access_endpoint_with_refreshed_token(
        self,
        api_endpoint
    ):
        """Test accessing protected endpoint with refreshed token"""
        print(f"\n[Test 12] Testing /user endpoint with refreshed token")

        assert TestAuthenticationFlow.new_id_token is not None, \
            "Refreshed token not available (test_11 must run first)"

        response = requests.get(
            f"{api_endpoint}/user",
            headers={"Authorization": f"Bearer {TestAuthenticationFlow.new_id_token}"}
        )

        assert response.status_code == 200, \
            f"Expected 200 OK with refreshed token, got {response.status_code}"

        user_data = response.json()
        assert 'user_id' in user_data, "Response missing user_id"

        print("✓ Refreshed token works for protected endpoint")

    @pytest.fixture(scope="class", autouse=True)
    def cleanup(
        self,
        request,
        cognito_client,
        user_pool_id,
        test_user_email
    ):
        """Cleanup: Delete test user after all tests complete"""
        yield  # Tests run here

        # Cleanup after all tests in the class
        print(f"\n[Cleanup] Deleting test user: {test_user_email}")
        try:
            cognito_client.admin_delete_user(
                UserPoolId=user_pool_id,
                Username=test_user_email
            )
            print("✓ Test user deleted successfully")
        except ClientError as e:
            print(f"⚠ Warning: Could not delete test user: {e}")


class TestPasswordPolicy:
    """Test password policy enforcement"""

    def test_weak_password_rejected(
        self,
        cognito_client,
        client_id
    ):
        """Test that weak passwords are rejected"""
        print(f"\n[Test] Testing weak password rejection")

        weak_passwords = [
            "short",  # Too short (< 12 chars)
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoNumbers!!",  # No numbers
            "NoSymbols123",  # No symbols
        ]

        for weak_pwd in weak_passwords:
            timestamp = int(datetime.now().timestamp() * 1000)
            test_email = f"weak+{timestamp}@example.com"

            with pytest.raises(ClientError) as exc_info:
                cognito_client.sign_up(
                    ClientId=client_id,
                    Username=test_email,
                    Password=weak_pwd,
                    UserAttributes=[
                        {'Name': 'email', 'Value': test_email}
                    ]
                )

            error_code = exc_info.value.response['Error']['Code']
            assert error_code == 'InvalidPasswordException', \
                f"Expected InvalidPasswordException for '{weak_pwd}', got {error_code}"

        print("✓ Weak passwords correctly rejected")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring deployed infrastructure"
    )


if __name__ == "__main__":
    # Allow running directly for manual testing
    required_vars = ['API_ENDPOINT', 'USER_POOL_ID', 'CLIENT_ID']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("\nUsage:")
        print("  export API_ENDPOINT=https://xxx.execute-api.us-east-1.amazonaws.com")
        print("  export USER_POOL_ID=us-east-1_xxxxxxxxx")
        print("  export CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("  python test_auth_flow.py")
        sys.exit(1)

    print("Testing authentication flow...")
    pytest.main([__file__, "-v", "-s"])
