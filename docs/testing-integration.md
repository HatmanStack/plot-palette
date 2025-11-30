# Integration Tests

Integration tests that require deployed AWS infrastructure.

## Prerequisites

- AWS infrastructure deployed (via `infrastructure/scripts/deploy.sh`)
- Environment variables set with stack outputs:
  - `API_ENDPOINT` - API Gateway endpoint URL
  - `USER_POOL_ID` - Cognito User Pool ID
  - `CLIENT_ID` - Cognito User Pool Client ID

## Running Tests

### Set Environment Variables

```bash
# Load from deployment outputs
export API_ENDPOINT=$(cat infrastructure/scripts/outputs.json | jq -r '.ApiEndpoint')
export USER_POOL_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolId')
export CLIENT_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolClientId')
```

### Run All Integration Tests

```bash
pytest tests/integration/ -v
```

### Run Specific Test Files

```bash
# CORS tests only
pytest tests/integration/test_cors.py -v

# Auth flow tests only
pytest tests/integration/test_auth_flow.py -v
```

### Run with Output

```bash
pytest tests/integration/ -v -s
```

## Test Files

- `test_cors.py` - CORS configuration tests (preflight and actual requests)
- `test_auth_flow.py` - End-to-end authentication flow tests
- `README.md` - This file

## Notes

- Integration tests require deployed infrastructure and will be skipped if environment variables are not set
- Tests create and delete temporary test users in Cognito
- API calls incur minimal AWS charges (typically < $0.01 per test run)
