# Testing Conventions

This guide establishes testing conventions for the Plot Palette codebase. Following these patterns ensures consistent, maintainable tests.

## Test File Organization

### Frontend (TypeScript/React)

Tests are co-located with source files:

```
frontend/src/
├── hooks/
│   ├── useAuth.ts
│   └── useAuth.test.ts        # Co-located test
├── contexts/
│   ├── AuthContext.tsx
│   └── AuthContext.test.tsx
├── components/
│   ├── JobCard.tsx
│   └── JobCard.test.tsx
└── test/
    ├── setup.ts               # Global test setup
    ├── test-utils.tsx         # Custom render, providers
    └── mocks/
        ├── auth.ts            # Auth service mocks
        ├── api.ts             # API service mocks
        └── react-query.tsx    # QueryClient wrapper
```

### Backend (Python)

Tests are organized by type in the `tests/` directory:

```
tests/
├── conftest.py                # Root fixtures (AWS mocks)
├── fixtures/
│   ├── __init__.py
│   ├── lambda_events.py       # API Gateway event factories
│   └── dynamodb_items.py      # DynamoDB item factories
├── unit/
│   ├── conftest.py            # Unit test fixtures
│   ├── test_shared.py         # Shared library tests
│   └── test_template_engine.py
└── integration/
    └── conftest.py            # Integration fixtures
```

## Test Structure

### Frontend: Describe-It Pattern

Use Vitest's `describe` and `it` blocks for clear organization:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '../test/test-utils'
import { JobCard } from './JobCard'

describe('JobCard', () => {
  describe('when job is running', () => {
    it('displays running status badge', () => {
      render(<JobCard job={runningJob} />)
      expect(screen.getByText('RUNNING')).toBeInTheDocument()
    })

    it('shows progress indicator', () => {
      render(<JobCard job={runningJob} />)
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })

  describe('when job is completed', () => {
    it('displays completed status badge', () => {
      render(<JobCard job={completedJob} />)
      expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    })
  })
})
```

### Backend: Class-Based Grouping

Use pytest classes to group related tests:

```python
import pytest
from backend.shared.utils import calculate_bedrock_cost

class TestBedrockCostCalculation:
    """Tests for Bedrock cost calculation."""

    def test_claude_input_tokens(self):
        """Test input token cost for Claude model."""
        cost = calculate_bedrock_cost(
            tokens=1_000_000,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            is_input=True,
        )
        assert cost == 3.00

    def test_unknown_model_raises_error(self):
        """Test error handling for unknown model."""
        with pytest.raises(ValueError, match="Unknown model ID"):
            calculate_bedrock_cost(tokens=1000, model_id="unknown", is_input=True)
```

### AAA Pattern (Arrange, Act, Assert)

Structure tests in three clear phases:

```python
def test_job_creation(self, mock_dynamodb_client):
    # Arrange
    event = make_create_job_event(
        template_id="template-123",
        seed_data_key="seed-data/test.json",
        budget_limit=50.0,
    )

    # Act
    result = handler(event, {})

    # Assert
    assert result["statusCode"] == 201
    assert "job-id" in json.loads(result["body"])
```

## Mocking Patterns

### Frontend: When to Use vi.mock() vs vi.spyOn()

**Use `vi.mock()` for:**
- Module-level mocking (services, libraries)
- External dependencies (axios, amazon-cognito-identity-js)
- When you want to replace the entire module

```typescript
// Mock entire module
vi.mock('../services/auth', () => ({
  signIn: vi.fn().mockResolvedValue('mock-token'),
  signOut: vi.fn(),
}))
```

**Use `vi.spyOn()` for:**
- Partial mocking (keep some real implementations)
- Watching function calls without replacing behavior
- When you need to restore original implementation

```typescript
// Spy on specific method
const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
// Test...
consoleSpy.mockRestore()
```

### Frontend: Using Mock Factories

```typescript
import { createAuthMock, authErrors } from '../test/mocks/auth'
import { createApiMock, sampleJobs } from '../test/mocks/api'

describe('useJobs', () => {
  it('handles auth errors', async () => {
    const authMock = createAuthMock({
      getIdTokenResult: authErrors.invalidCredentials,
    })
    vi.mock('../services/auth', () => authMock)
    // Test error handling...
  })

  it('fetches jobs successfully', async () => {
    const apiMock = createApiMock({
      fetchJobsResult: sampleJobs,
    })
    vi.mock('../services/api', () => apiMock)
    // Test success case...
  })
})
```

### Backend: Using Fixtures and Factories

```python
from tests.fixtures import make_api_gateway_event_v2, make_job_item

class TestGetJob:
    def test_get_existing_job(self, mock_dynamodb_client):
        # Use factories for test data
        job_item = make_job_item(
            job_id="job-123",
            user_id="user-456",
            status="RUNNING",
        )
        mock_dynamodb_client.get_item.return_value = {"Item": job_item}

        event = make_api_gateway_event_v2(
            method="GET",
            path="/jobs/job-123",
            path_parameters={"jobId": "job-123"},
            user_id="user-456",
        )

        result = handler(event, {})
        assert result["statusCode"] == 200
```

### Resetting Mocks Between Tests

**Frontend:** Handled automatically in `setup.ts`:
```typescript
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
```

**Backend:** Use pytest fixtures with function scope:
```python
@pytest.fixture
def mock_dynamodb_client():
    client = MagicMock()
    # Setup...
    return client  # Fresh instance per test
```

## Assertion Patterns

### Frontend: Prefer Specific jest-dom Matchers

```typescript
// Good - specific assertion
expect(screen.getByRole('button')).toBeDisabled()
expect(screen.getByText('Error')).toBeVisible()
expect(element).toHaveClass('active')

// Avoid - generic assertions
expect(screen.getByRole('button').disabled).toBe(true)
expect(element.classList.contains('active')).toBe(true)
```

### Backend: Use Descriptive Assertions

```python
# Good - clear assertions with context
assert result["statusCode"] == 200, f"Expected 200, got {result['statusCode']}"
assert "job_id" in response, "Response should contain job_id"

# Good - pytest.approx for floats
assert cost == pytest.approx(3.50, rel=1e-6)

# Avoid - bare assertions without context
assert result["statusCode"] == 200
```

## Async Testing

### Frontend: waitFor and findBy Queries

```typescript
import { render, screen, waitFor } from '../test/test-utils'

it('loads jobs asynchronously', async () => {
  render(<JobsList />)

  // Wait for loading to complete
  await waitFor(() => {
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
  })

  // Or use findBy (combines getBy + waitFor)
  const jobCard = await screen.findByTestId('job-card')
  expect(jobCard).toBeInTheDocument()
})
```

### Backend: pytest-asyncio

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

## Common Gotchas

### 1. Forgetting to Clean Up

**Frontend:** Always use the custom `render` from `test-utils.tsx` - it handles cleanup automatically.

**Backend:** Use fixtures with appropriate scope:
```python
@pytest.fixture  # Default function scope - clean per test
def fresh_client():
    return MagicMock()

@pytest.fixture(scope="session")  # Use carefully - shared across tests
def expensive_resource():
    return setup_resource()
```

### 2. Test Interdependence

**Problem:** Test B depends on state from Test A.

**Solution:** Each test should set up its own state:
```python
# Bad - relies on previous test
def test_update_job():
    job_id = "from-previous-test"  # Don't do this

# Good - self-contained
def test_update_job(mock_dynamodb_client, sample_job_config):
    job_item = make_job_item(**sample_job_config)
    mock_dynamodb_client.get_item.return_value = {"Item": job_item}
```

### 3. Mocking Too Much or Too Little

**Over-mocking:** Testing mocks instead of real behavior
```python
# Bad - testing the mock
def test_get_user(mock_cognito):
    mock_cognito.get_user.return_value = {"Username": "test"}
    result = mock_cognito.get_user()  # Just testing the mock!
    assert result["Username"] == "test"
```

**Under-mocking:** Tests require real AWS resources
```python
# Bad - requires real credentials
def test_upload_file():
    s3_client = boto3.client("s3")  # Will fail without AWS creds
```

### 4. Flaky Async Tests

**Problem:** Tests pass sometimes, fail others.

**Solution:** Use explicit waits, not timers:
```typescript
// Bad - arbitrary timeout
await new Promise(resolve => setTimeout(resolve, 100))

// Good - wait for specific condition
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument()
})
```

### 5. Testing Implementation Details

**Problem:** Tests break when refactoring, even if behavior unchanged.

```typescript
// Bad - tests internal state
expect(component.state.isLoading).toBe(false)

// Good - tests user-visible behavior
expect(screen.getByText('Jobs')).toBeInTheDocument()
expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
```

## Running Tests

```bash
# Run all checks (lint + tests)
npm run check

# Frontend tests only
cd frontend && npm test

# Frontend watch mode
cd frontend && npm run test:watch

# Backend tests only
PYTHONPATH=. pytest tests/unit tests/integration -v

# Backend with coverage
PYTHONPATH=. pytest tests/ --cov=backend --cov-report=term-missing
```

## Coverage Targets

| Area | Current | Target |
|------|---------|--------|
| Frontend | ~0% | ~70% |
| Backend | ~60% | ~80% |

Focus coverage on:
- Business logic
- Error handling paths
- Edge cases

Don't obsess over:
- Simple getters/setters
- Framework boilerplate
- Pure UI styling
