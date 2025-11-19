# Phase 2: Authentication & API Gateway

## Phase Goal

Implement user authentication with Amazon Cognito User Pools and create HTTP API Gateway with JWT authorization. By the end of this phase, users can sign up, log in, and the API infrastructure will be ready to receive authenticated requests from the frontend.

**Success Criteria:**
- Cognito User Pool configured with email verification and password policies
- Cognito User Pool Client created for web application
- HTTP API Gateway deployed with JWT authorizer
- Lambda functions for health check and user info endpoints
- API Gateway CORS configured for frontend access
- All endpoints tested with authenticated requests

**Estimated Tokens:** ~88,000

---

## Prerequisites

- **Phase 1** completed (VPC, S3, DynamoDB, IAM roles deployed)
- AWS CLI configured
- Python 3.13 virtualenv activated
- Understanding of JWT authentication flow
- Postman or curl for API testing

---

## Task 1: Cognito User Pool Stack

### Goal

Create Amazon Cognito User Pool with secure password policies, email verification, and MFA support (optional). Configure user pool client for the web application.

### Files to Create

- `infrastructure/cloudformation/auth-stack.yaml` - Cognito User Pool template

### Prerequisites

- Phase 1 IAM stack deployed (AmplifyServiceRole may need Cognito permissions)
- Valid email configured in AWS SES for sending verification emails (or use Cognito default)

### Implementation Steps

1. **Create Cognito User Pool resource:**
   - Pool name: `plot-palette-users-{EnvironmentName}`
   - **Username attributes:** Email (users sign in with email)
   - **Auto-verified attributes:** Email
   - **Password policy:**
     - Minimum length: 12 characters
     - Require uppercase: true
     - Require lowercase: true
     - Require numbers: true
     - Require symbols: true
     - Temporary password validity: 7 days
   - **MFA configuration:** Optional (user choice)
   - **Account recovery:** Email only

2. **Configure email settings:**
   - **Email verification message:**
     - Subject: "Verify your Plot Palette account"
     - Message: "Your verification code is {####}"
   - **Email sending:** Use Cognito default (or SES if configured)
   - **From email:** `no-reply@verificationemail.com` (Cognito default)

3. **Add custom attributes:**
   - `custom:user_role` (String) - "admin" or "user" (for future RBAC)
   - `custom:organization` (String) - for multi-tenant support (optional)

4. **Configure user pool policies:**
   - **Sign-up:** Allow users to sign themselves up
   - **Admin create user:** Allowed
   - **Case sensitivity:** False (email matching is case-insensitive)

5. **Create User Pool Client:**
   - Client name: `plot-palette-web-client`
   - **Auth flows:** `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`
   - **Prevent user existence errors:** Enabled (don't reveal if user exists)
   - **Token validity:**
     - ID token: 60 minutes
     - Access token: 60 minutes
     - Refresh token: 30 days
   - **Read attributes:** email, name, custom:user_role
   - **Write attributes:** name, custom:user_role
   - **No client secret** (for web apps, client secret not needed)

6. **Add Lambda triggers (optional for Phase 2, can add later):**
   - Pre-signup: Validate email domain (if restricting to certain domains)
   - Post-confirmation: Create user record in DynamoDB
   - For now, skip triggers - add in future phases if needed

7. **Add CloudFormation Outputs:**
   - User Pool ID
   - User Pool ARN
   - User Pool Client ID
   - User Pool Domain (if using Hosted UI)

### Verification Checklist

- [ ] User Pool created with correct name
- [ ] Password policy enforces 12+ chars with complexity requirements
- [ ] Email verification required
- [ ] MFA optional (users can enable)
- [ ] User Pool Client created without client secret
- [ ] Token expiration configured (60min access, 30day refresh)
- [ ] Custom attributes defined
- [ ] Auto sign-up enabled
- [ ] Outputs exported

### Testing Instructions

**Unit Test:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/auth-stack.yaml
```

**Integration Test:**
```bash
# Deploy stack
aws cloudformation create-stack \
  --stack-name plot-palette-auth-test \
  --template-body file://infrastructure/cloudformation/auth-stack.yaml \
  --parameters ParameterKey=EnvironmentName,ParameterValue=test

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-auth-test

# Get outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-auth-test \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-auth-test \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
  --output text)

# Test user signup
aws cognito-idp sign-up \
  --client-id $CLIENT_ID \
  --username test@example.com \
  --password TestPassword123! \
  --user-attributes Name=email,Value=test@example.com Name=name,Value="Test User"

# Verify email (in real scenario, user receives code via email)
# For testing, admin confirm user
aws cognito-idp admin-confirm-sign-up \
  --user-pool-id $USER_POOL_ID \
  --username test@example.com

# Test login
aws cognito-idp initiate-auth \
  --client-id $CLIENT_ID \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123!

# Cleanup
aws cognito-idp admin-delete-user \
  --user-pool-id $USER_POOL_ID \
  --username test@example.com

aws cloudformation delete-stack --stack-name plot-palette-auth-test
```

### Commit Message Template

```
feat(auth): add Cognito User Pool for authentication

- Create User Pool with email sign-in and verification
- Configure secure password policy (12+ chars, complexity)
- Add User Pool Client for web application
- Set token expiration (60min access, 30day refresh)
- Enable optional MFA and account recovery
- Add custom attributes for user roles

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 2: HTTP API Gateway Stack

### Goal

Create HTTP API Gateway (v2) with routes for health check and user authentication. Configure JWT authorizer using Cognito User Pool.

### Files to Create

- `infrastructure/cloudformation/api-stack.yaml` - API Gateway template

### Prerequisites

- Task 1 completed (Cognito User Pool deployed)
- Understanding of API Gateway v2 (HTTP API) vs v1 (REST API)

### Implementation Steps

1. **Create HTTP API resource:**
   - API name: `plot-palette-api-{EnvironmentName}`
   - Protocol type: HTTP
   - CORS configuration:
     - Allow origins: `*` (will restrict to Amplify domain in Phase 6)
     - Allow methods: GET, POST, PUT, DELETE, OPTIONS
     - Allow headers: `Content-Type`, `Authorization`, `X-Amz-Date`, `X-Api-Key`, `X-Amz-Security-Token`
     - Max age: 300 seconds
   - Description: "Plot Palette API for synthetic data generation"

2. **Create JWT Authorizer:**
   - Authorizer name: `cognito-jwt-authorizer`
   - Identity source: `$request.header.Authorization`
   - Issuer URL: `https://cognito-idp.{region}.amazonaws.com/{UserPoolId}`
   - Audience: `{UserPoolClientId}` (from Cognito stack)
   - Authorizer type: JWT
   - JWT configuration validates:
     - Token signature (using Cognito public keys)
     - Token expiration
     - Audience matches client ID

3. **Create API stages:**
   - **$default stage:** Auto-deployment enabled
   - Stage variables (for future use): `environment=production`
   - Throttling: 1000 requests per second (default)
   - Access logging: CloudWatch Logs (create log group)

4. **Create routes (initial set for Phase 2):**
   - `GET /health` - Health check endpoint (no auth required)
   - `GET /user` - Get current user info (requires auth)
   - Additional routes will be added in Phase 3

5. **Add CloudWatch logging:**
   - Create CloudWatch Log Group: `/aws/apigateway/plot-palette-api`
   - Retention: 7 days (for cost optimization)
   - Log format: JSON with request ID, caller IP, status code

6. **Add CloudFormation Parameters:**
   - `UserPoolId` (from auth stack)
   - `UserPoolClientId` (from auth stack)
   - `EnvironmentName`

7. **Add CloudFormation Outputs:**
   - API Gateway ID
   - API Gateway endpoint URL (e.g., `https://abc123.execute-api.us-east-1.amazonaws.com`)
   - API Gateway stage name

### Verification Checklist

- [ ] HTTP API created with correct name
- [ ] JWT authorizer configured with Cognito User Pool
- [ ] CORS enabled for all required origins and methods
- [ ] Routes created for /health and /user
- [ ] CloudWatch logging enabled
- [ ] $default stage auto-deploys on changes
- [ ] Outputs exported

### Testing Instructions

**Unit Test:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/api-stack.yaml
```

**Integration Test:**
```bash
# Deploy with Cognito User Pool parameters
aws cloudformation create-stack \
  --stack-name plot-palette-api-test \
  --template-body file://infrastructure/cloudformation/api-stack.yaml \
  --parameters \
    ParameterKey=UserPoolId,ParameterValue=$USER_POOL_ID \
    ParameterKey=UserPoolClientId,ParameterValue=$CLIENT_ID \
    ParameterKey=EnvironmentName,ParameterValue=test

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-api-test

# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-api-test \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

# Test health endpoint (no auth)
curl $API_ENDPOINT/health

# Test authenticated endpoint (should return 401 without token)
curl $API_ENDPOINT/user

# Get token from Cognito (using test user from Task 1)
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id $CLIENT_ID \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123! \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# Test with token (should return 404 because Lambda not connected yet)
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/user

# Cleanup
aws cloudformation delete-stack --stack-name plot-palette-api-test
```

### Commit Message Template

```
feat(api): add HTTP API Gateway with JWT authorization

- Create HTTP API Gateway v2 for REST endpoints
- Configure JWT authorizer with Cognito User Pool
- Enable CORS for cross-origin requests
- Add initial routes (/health, /user)
- Configure CloudWatch logging for requests
- Create $default stage with auto-deployment

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~13,000

---

## Task 3: Lambda Function - Health Check

### Goal

Create a simple Lambda function to handle the `/health` endpoint, verifying API Gateway and Lambda integration works correctly.

### Files to Create

- `backend/lambdas/health/handler.py` - Health check Lambda handler
- `backend/lambdas/health/requirements.txt` - Dependencies (minimal)

### Prerequisites

- Task 2 completed (API Gateway deployed)
- Phase 1 Task 6 completed (shared library)
- Python 3.13 available

### Implementation Steps

1. **Create handler function:**
   - Return HTTP 200 with JSON body
   - Include timestamp, version, status
   - No external dependencies needed (keep it simple)
   - Use structured logging

2. **Handler structure:**
   ```python
   import json
   import logging
   from datetime import datetime

   logger = logging.getLogger()
   logger.setLevel(logging.INFO)

   def lambda_handler(event, context):
       """Health check endpoint - returns API status"""
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
   ```

3. **Create minimal requirements.txt:**
   - No external dependencies needed for health check

4. **Create deployment package:**
   - Lambda will be deployed via CloudFormation
   - Code can be inline for now (small enough)
   - In Phase 7, we'll use SAM or zip deployment

5. **Update API Gateway stack to connect Lambda:**
   - Create Lambda resource in api-stack.yaml
   - Create Lambda permission for API Gateway to invoke
   - Create API Gateway integration for `GET /health` route
   - Target: Lambda function ARN

### Verification Checklist

- [ ] Handler function created with correct signature
- [ ] Returns 200 status code with JSON body
- [ ] Includes timestamp and version in response
- [ ] Structured logging implemented
- [ ] CORS headers included in response
- [ ] No errors when invoked locally
- [ ] API Gateway integration configured

### Testing Instructions

**Unit Test (create `tests/unit/test_health.py`):**
```python
import json
from backend.lambdas.health.handler import lambda_handler

class MockContext:
    request_id = "test-request-id"

def test_health_check():
    event = {}
    context = MockContext()

    response = lambda_handler(event, context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert body["version"] == "1.0.0"

# Run: pytest tests/unit/test_health.py -v
```

**Local Test:**
```bash
# Test locally with SAM (if installed)
echo '{}' | sam local invoke HealthCheckFunction

# Or test with Python directly
python3.13 -c "
from backend.lambdas.health.handler import lambda_handler
class Context:
    request_id = 'local-test'
print(lambda_handler({}, Context()))
"
```

**Integration Test (after deployment):**
```bash
# Invoke via API Gateway
curl https://{api-id}.execute-api.{region}.amazonaws.com/health

# Expected output:
# {
#   "status": "healthy",
#   "timestamp": "2025-11-19T10:00:00.000000",
#   "version": "1.0.0",
#   "service": "plot-palette-api"
# }
```

### Commit Message Template

```
feat(lambda): add health check endpoint

- Create Lambda function for /health endpoint
- Return service status, version, and timestamp
- Implement structured JSON logging
- Add CORS headers for cross-origin requests
- Connect to API Gateway with Lambda integration

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~10,000

---

## Task 4: Lambda Function - Get User Info

### Goal

Create Lambda function to return authenticated user information from Cognito JWT token, demonstrating JWT authorizer integration.

### Files to Create

- `backend/lambdas/user/handler.py` - User info Lambda handler
- `backend/lambdas/user/requirements.txt` - Dependencies

### Prerequisites

- Task 1 completed (Cognito User Pool)
- Task 2 completed (API Gateway with JWT authorizer)
- Task 3 completed (Health check Lambda pattern)
- Understanding of JWT claims structure

### Implementation Steps

1. **Create handler function:**
   - Extract user claims from `event['requestContext']['authorizer']['jwt']['claims']`
   - Return user information (email, sub/user_id, custom attributes)
   - Handle missing or invalid claims
   - Use shared library for structured logging

2. **Handler structure:**
   ```python
   import json
   import logging
   from backend.shared.utils import setup_logger

   logger = setup_logger(__name__)

   def lambda_handler(event, context):
       """Get current user information from JWT claims"""
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
   ```

3. **Add to requirements.txt:**
   - Reference `../shared` for shared library

4. **Update API Gateway stack:**
   - Create Lambda resource for user info function
   - Attach JWT authorizer to `GET /user` route
   - Create Lambda permission for API Gateway
   - Configure integration

5. **Update IAM role:**
   - Ensure LambdaExecutionRole from Phase 1 has CloudWatch Logs permissions
   - No additional permissions needed (reading JWT claims doesn't require Cognito API access)

### Verification Checklist

- [ ] Handler extracts JWT claims correctly
- [ ] Returns user information (ID, email, role)
- [ ] Returns 401 if claims missing
- [ ] Returns 500 on errors with logging
- [ ] CORS headers included
- [ ] Connected to API Gateway with authorizer
- [ ] Unit tests pass
- [ ] Integration test with real JWT token works

### Testing Instructions

**Unit Test (create `tests/unit/test_user.py`):**
```python
import json
from backend.lambdas.user.handler import lambda_handler

class MockContext:
    request_id = "test-request-id"

def test_user_info_success():
    event = {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "user-123",
                        "email": "test@example.com",
                        "email_verified": "true",
                        "custom:user_role": "admin"
                    }
                }
            }
        }
    }
    context = MockContext()

    response = lambda_handler(event, context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["user_id"] == "user-123"
    assert body["email"] == "test@example.com"
    assert body["role"] == "admin"

def test_user_info_unauthorized():
    event = {}
    context = MockContext()

    response = lambda_handler(event, context)

    assert response["statusCode"] == 401

# Run: pytest tests/unit/test_user.py -v
```

**Integration Test:**
```bash
# Sign up and confirm user (from Task 1)
aws cognito-idp sign-up \
  --client-id $CLIENT_ID \
  --username test@example.com \
  --password TestPassword123! \
  --user-attributes Name=email,Value=test@example.com

aws cognito-idp admin-confirm-sign-up \
  --user-pool-id $USER_POOL_ID \
  --username test@example.com

# Get ID token
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id $CLIENT_ID \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123! \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# Call /user endpoint with token
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/user

# Expected output:
# {
#   "user_id": "abc-123-def",
#   "email": "test@example.com",
#   "email_verified": true,
#   "role": "user",
#   ...
# }
```

### Commit Message Template

```
feat(lambda): add get user info endpoint with JWT authorization

- Create Lambda function to extract user data from JWT claims
- Return user ID, email, role, and token metadata
- Handle unauthorized requests with 401 response
- Implement error handling and structured logging
- Configure API Gateway integration with JWT authorizer

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 5: Update Deployment Script for Auth and API

### Goal

Update the deployment script from Phase 1 to include Cognito and API Gateway stacks with proper dependency management.

### Files to Modify

- `infrastructure/scripts/deploy.sh` - Add auth and api stacks

### Prerequisites

- Tasks 1-4 completed (all templates and Lambda functions created)
- Phase 1 deployment script working

### Implementation Steps

1. **Add new stack deployments to script:**
   - Deploy auth stack (no dependencies beyond Phase 1)
   - Deploy api stack (depends on auth stack outputs)
   - Update dependency chain in comments

2. **Pass Cognito outputs to API stack:**
   - Query auth stack for UserPoolId and UserPoolClientId
   - Pass as parameters to api-stack.yaml

3. **Add Lambda deployment:**
   - Package Lambda functions (zip files or inline code)
   - Upload to S3 bucket (from Phase 1 storage stack)
   - Reference in CloudFormation template

4. **Update outputs.json:**
   - Include Cognito User Pool details
   - Include API Gateway endpoint URL
   - Include User Pool Client ID (needed for frontend in Phase 6)

5. **Add validation steps:**
   - After API deployment, test /health endpoint
   - Display API endpoint URL prominently
   - Show next steps (create user, get token)

6. **Handle Lambda code updates:**
   - Function to package Lambda code into zip
   - Upload to S3 with versioned key
   - Update Lambda function code reference in CFN

### Verification Checklist

- [ ] Script deploys auth stack successfully
- [ ] Script deploys api stack with correct parameters
- [ ] Lambda functions packaged and uploaded to S3
- [ ] API Gateway integration works (health check returns 200)
- [ ] Outputs.json includes all new stack outputs
- [ ] Script handles errors gracefully
- [ ] Can run script multiple times (idempotent)

### Testing Instructions

**Test deployment:**
```bash
# Full deployment
./infrastructure/scripts/deploy.sh --region us-east-1 --environment test

# Verify auth stack
aws cognito-idp describe-user-pool --user-pool-id <from outputs>

# Verify API
API_ENDPOINT=$(cat infrastructure/scripts/outputs.json | jq -r '.ApiEndpoint')
curl $API_ENDPOINT/health

# Test authenticated endpoint
# (Requires creating user and getting token - see Task 4)

# Cleanup
./infrastructure/scripts/deploy.sh --delete --environment test
```

### Commit Message Template

```
feat(deploy): update deployment script for auth and API stacks

- Add Cognito User Pool stack deployment
- Add API Gateway stack with dependency on auth stack
- Package and upload Lambda functions to S3
- Pass Cognito outputs to API Gateway parameters
- Update outputs.json with API endpoint and User Pool details
- Add health check validation after deployment

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~9,000

---

## Task 6: CORS Configuration Testing

### Goal

Thoroughly test CORS configuration to ensure frontend (Amplify) can make cross-origin requests to API Gateway.

### Files to Create

- `tests/integration/test_cors.py` - CORS integration tests

### Prerequisites

- Task 2 completed (API Gateway with CORS)
- API Gateway deployed
- Understanding of CORS preflight requests

### Implementation Steps

1. **Create CORS test script:**
   - Test OPTIONS preflight request
   - Verify Access-Control-Allow-Origin header
   - Verify Access-Control-Allow-Methods header
   - Verify Access-Control-Allow-Headers header
   - Test actual GET/POST requests with Origin header

2. **Test preflight (OPTIONS) request:**
   ```python
   import requests

   def test_cors_preflight(api_endpoint):
       response = requests.options(
           f"{api_endpoint}/health",
           headers={
               "Origin": "http://localhost:5173",  # Vite dev server
               "Access-Control-Request-Method": "GET",
               "Access-Control-Request-Headers": "Content-Type,Authorization"
           }
       )

       assert response.status_code == 200
       assert "Access-Control-Allow-Origin" in response.headers
       assert "Access-Control-Allow-Methods" in response.headers
       assert "GET" in response.headers["Access-Control-Allow-Methods"]
   ```

3. **Test actual request with Origin:**
   ```python
   def test_cors_actual_request(api_endpoint):
       response = requests.get(
           f"{api_endpoint}/health",
           headers={"Origin": "http://localhost:5173"}
       )

       assert response.status_code == 200
       assert response.headers.get("Access-Control-Allow-Origin") == "*"
   ```

4. **Test with different origins:**
   - Localhost (development)
   - Amplify domain (will be known in Phase 6)
   - Verify wildcard (*) works for all

5. **Document CORS configuration:**
   - Add comments to API Gateway template explaining CORS settings
   - Note that wildcard will be restricted to Amplify domain in Phase 6

### Verification Checklist

- [ ] OPTIONS preflight returns correct CORS headers
- [ ] Actual requests include Access-Control-Allow-Origin
- [ ] Multiple origins tested (localhost, example domains)
- [ ] All HTTP methods allowed (GET, POST, PUT, DELETE)
- [ ] Authorization header allowed
- [ ] Tests automated and repeatable

### Testing Instructions

**Manual CORS test with curl:**
```bash
# Test preflight
curl -X OPTIONS $API_ENDPOINT/health \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -v

# Check response headers for:
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS
# Access-Control-Allow-Headers: Content-Type,Authorization,...

# Test actual request
curl $API_ENDPOINT/health \
  -H "Origin: http://localhost:5173" \
  -v

# Verify Access-Control-Allow-Origin in response
```

**Automated test:**
```bash
pytest tests/integration/test_cors.py -v --api-endpoint=$API_ENDPOINT
```

### Commit Message Template

```
test(api): add CORS integration tests

- Create test suite for CORS preflight requests
- Verify Access-Control headers on OPTIONS and actual requests
- Test multiple origins (localhost, Amplify)
- Ensure all required methods and headers allowed
- Document CORS configuration for frontend integration

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~8,000

---

## Task 7: End-to-End Authentication Flow Test

### Goal

Create a comprehensive test that validates the entire authentication flow: sign up → email verification → login → access protected endpoint.

### Files to Create

- `tests/integration/test_auth_flow.py` - Complete auth flow test
- `tests/fixtures/test_users.json` - Test user data

### Prerequisites

- All previous Phase 2 tasks completed
- Cognito User Pool deployed
- API Gateway deployed with /user endpoint

### Implementation Steps

1. **Create test script for complete flow:**
   - Sign up new user
   - Admin confirm user (simulating email verification)
   - Login to get tokens
   - Call protected /user endpoint with token
   - Verify user data returned
   - Cleanup (delete test user)

2. **Test structure:**
   ```python
   import boto3
   import requests
   import json
   import pytest
   from datetime import datetime

   class TestAuthFlow:
       def setup_class(self):
           self.cognito = boto3.client('cognito-idp')
           self.user_pool_id = os.getenv('USER_POOL_ID')
           self.client_id = os.getenv('CLIENT_ID')
           self.api_endpoint = os.getenv('API_ENDPOINT')
           self.test_email = f"test+{datetime.now().timestamp()}@example.com"

       def test_01_signup(self):
           # Test user signup
           response = self.cognito.sign_up(
               ClientId=self.client_id,
               Username=self.test_email,
               Password="TestPassword123!",
               UserAttributes=[
                   {'Name': 'email', 'Value': self.test_email},
                   {'Name': 'name', 'Value': 'Test User'}
               ]
           )
           assert 'UserSub' in response

       def test_02_confirm_signup(self):
           # Admin confirm (simulates email verification)
           self.cognito.admin_confirm_sign_up(
               UserPoolId=self.user_pool_id,
               Username=self.test_email
           )

       def test_03_login(self):
           # Login and get tokens
           response = self.cognito.initiate_auth(
               ClientId=self.client_id,
               AuthFlow='USER_PASSWORD_AUTH',
               AuthParameters={
                   'USERNAME': self.test_email,
                   'PASSWORD': 'TestPassword123!'
               }
           )
           self.id_token = response['AuthenticationResult']['IdToken']
           self.access_token = response['AuthenticationResult']['AccessToken']
           self.refresh_token = response['AuthenticationResult']['RefreshToken']

           assert self.id_token is not None

       def test_04_access_protected_endpoint(self):
           # Call /user endpoint with token
           response = requests.get(
               f"{self.api_endpoint}/user",
               headers={'Authorization': f'Bearer {self.id_token}'}
           )

           assert response.status_code == 200
           user_data = response.json()
           assert user_data['email'] == self.test_email

       def test_05_refresh_token(self):
           # Test refresh token flow
           response = self.cognito.initiate_auth(
               ClientId=self.client_id,
               AuthFlow='REFRESH_TOKEN_AUTH',
               AuthParameters={
                   'REFRESH_TOKEN': self.refresh_token
               }
           )

           new_id_token = response['AuthenticationResult']['IdToken']
           assert new_id_token != self.id_token

       def teardown_class(self):
           # Cleanup test user
           try:
               self.cognito.admin_delete_user(
                   UserPoolId=self.user_pool_id,
                   Username=self.test_email
               )
           except:
               pass
   ```

3. **Add test for invalid scenarios:**
   - Login with wrong password (should fail)
   - Access protected endpoint without token (should return 401)
   - Access with expired token (should return 401)
   - Access with malformed token (should return 401)

4. **Create test configuration:**
   - Use pytest fixtures for API endpoint and Cognito IDs
   - Load from environment variables or outputs.json

5. **Document test execution:**
   - Add README in tests/integration/ explaining how to run
   - List required environment variables

### Verification Checklist

- [ ] Test signs up new user successfully
- [ ] Test confirms user (simulated email verification)
- [ ] Test logs in and receives tokens
- [ ] Test accesses protected endpoint with valid token
- [ ] Test refreshes token successfully
- [ ] Test handles invalid credentials correctly
- [ ] Test handles missing/invalid tokens correctly
- [ ] Cleanup removes test users

### Testing Instructions

**Set environment variables:**
```bash
export USER_POOL_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolId')
export CLIENT_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolClientId')
export API_ENDPOINT=$(cat infrastructure/scripts/outputs.json | jq -r '.ApiEndpoint')
```

**Run tests:**
```bash
pytest tests/integration/test_auth_flow.py -v -s
```

**Expected output:**
```
tests/integration/test_auth_flow.py::TestAuthFlow::test_01_signup PASSED
tests/integration/test_auth_flow.py::TestAuthFlow::test_02_confirm_signup PASSED
tests/integration/test_auth_flow.py::TestAuthFlow::test_03_login PASSED
tests/integration/test_auth_flow.py::TestAuthFlow::test_04_access_protected_endpoint PASSED
tests/integration/test_auth_flow.py::TestAuthFlow::test_05_refresh_token PASSED
```

### Commit Message Template

```
test(auth): add end-to-end authentication flow tests

- Create comprehensive test for signup → verify → login → access
- Test token refresh flow
- Add negative tests for invalid credentials and tokens
- Implement automatic test user cleanup
- Document test execution with environment variables

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Phase 2 Verification

After completing all tasks, verify the entire phase:

### Integration Tests

1. **Deploy complete Phase 2 infrastructure:**
   ```bash
   ./infrastructure/scripts/deploy.sh --region us-east-1 --environment phase2-test
   ```

2. **Verify Cognito:**
   ```bash
   aws cognito-idp describe-user-pool --user-pool-id <pool-id>
   aws cognito-idp describe-user-pool-client --user-pool-id <pool-id> --client-id <client-id>
   ```

3. **Verify API Gateway:**
   ```bash
   aws apigatewayv2 get-apis
   aws apigatewayv2 get-routes --api-id <api-id>
   aws apigatewayv2 get-authorizers --api-id <api-id>
   ```

4. **Test health endpoint:**
   ```bash
   curl https://<api-id>.execute-api.<region>.amazonaws.com/health
   ```

5. **Test complete auth flow:**
   ```bash
   pytest tests/integration/test_auth_flow.py -v
   ```

6. **Test CORS:**
   ```bash
   pytest tests/integration/test_cors.py -v
   ```

### Success Criteria

- [ ] Cognito User Pool created with correct policies
- [ ] User Pool Client configured for web app
- [ ] HTTP API Gateway deployed
- [ ] JWT authorizer configured and working
- [ ] /health endpoint returns 200 without auth
- [ ] /user endpoint requires valid JWT token
- [ ] /user endpoint returns correct user data from token
- [ ] CORS headers present on all responses
- [ ] Complete auth flow test passes
- [ ] Lambda functions log to CloudWatch
- [ ] Deployment script handles all Phase 2 stacks

### Estimated Total Cost (Phase 2 running for 1 hour)

- Cognito: $0 (50,000 MAU free tier)
- API Gateway: $0 (1M requests free tier)
- Lambda: $0 (1M requests free tier, minimal invocations)
- CloudWatch Logs: $0.01 (minimal logs)
- **Total: ~$0.01/hour**

---

## Known Limitations & Technical Debt

1. **CORS Wildcard:** Currently allowing all origins (*), will restrict to Amplify domain in Phase 6
2. **No Rate Limiting:** API Gateway throttling at default 1000 req/sec, may need per-user quotas later
3. **Inline Lambda Code:** Small functions use inline code in CFN, larger functions in Phase 3+ will use S3
4. **No Custom Domain:** Using default API Gateway domain, can add custom domain in future
5. **No WAF:** No Web Application Firewall yet, can add if needed for production
6. **Admin User Confirmation:** Using admin confirm for tests, real flow requires email with verification code

---

## Next Steps

With authentication and API infrastructure in place, you're ready to proceed to **Phase 3: Backend APIs & Job Management**.

Phase 3 will add:
- Lambda functions for creating and managing generation jobs
- Job queue management with DynamoDB
- Seed data upload with presigned S3 URLs
- Prompt template CRUD operations
- Real-time job status queries
- Cost calculation APIs

---

**Navigation:**
- [← Back to README](./README.md)
- [← Previous: Phase 1](./Phase-1.md)
- [Next: Phase 3 - Backend APIs & Job Management →](./Phase-3.md)
