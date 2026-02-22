# Troubleshooting

## Bedrock `AccessDeniedException`

**Cause:** The Bedrock model has not been enabled in your AWS region.

**Fix:** Go to AWS Console > Amazon Bedrock > Model access and request access for the required models. See [AWS Setup](aws-setup.md#enable-bedrock-models).

## Cognito `NotAuthorizedException`

**Cause:** Invalid credentials, expired token, or user not confirmed.

**Fix:** Verify the user exists in the Cognito User Pool and has a permanent password set. Check that `VITE_USER_POOL_ID` and `VITE_USER_POOL_CLIENT_ID` in `.env` match the deployed stack outputs.

## `PYTHONPATH` Test Errors

**Cause:** Backend tests import from `backend.shared` which requires the repo root on `PYTHONPATH`.

**Fix:** Run tests from the repo root with the path set:
```bash
PYTHONPATH=. pytest tests/unit tests/integration -v
```

## `ModuleNotFoundError: moto` or `ModuleNotFoundError: pyarrow`

**Cause:** Dev or worker dependencies not installed.

**Fix:**
```bash
cd backend && uv pip install -e ".[dev,worker]" --system
```

## LocalStack E2E Test Failures

**Cause:** Docker not running, or LocalStack container failed to start.

**Fix:** Ensure Docker is running, then:
```bash
docker compose down -v   # Clean up stale state
npm run test:e2e         # Retry
```

## Pre-commit Hook Failures

**Cause:** Hooks not installed, or dependencies missing.

**Fix:**
```bash
pre-commit install                    # Install hooks
pre-commit run --all-files            # Test all hooks
npm install                           # If commitlint fails
cd backend && uv pip install ruff     # If ruff fails
```
