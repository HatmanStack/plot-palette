# Plot Palette Test Suite

Comprehensive testing infrastructure for Plot Palette with unit, integration, E2E, and performance tests.

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 20+
- AWS CLI configured (for integration tests only)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd plot-palette

# Install backend package in development mode
pip install -e .[dev]

# Install frontend dependencies (for E2E tests)
cd frontend
npm install
cd ..

# Install Playwright browsers (for E2E tests)
npx playwright install
```

### Running Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage report
pytest tests/unit/ --cov=backend --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_template_engine.py -v

# Run integration tests (requires mocked AWS services)
pytest tests/integration/ -v

# Run E2E tests (requires deployed frontend)
npx playwright test

# Run performance tests
locust -f tests/performance/locustfile.py --host=$API_ENDPOINT
```

## Project Structure

```
tests/
├── unit/                       # Unit tests (fast, no external dependencies)
│   ├── test_shared.py          # Models, constants, utils
│   ├── test_template_engine.py # Template rendering and filters
│   ├── test_cost_calculation.py # Cost tracking and budget enforcement
│   ├── test_template_filters.py # Custom Jinja2 filters
│   ├── test_health.py          # Health check endpoints
│   └── test_user.py            # User management
│
├── integration/                # Integration tests (mocked AWS services)
│   ├── conftest.py             # Shared fixtures
│   ├── test_worker.py          # ECS worker job processing
│   ├── test_checkpoint.py      # Checkpoint save/restore
│   ├── test_budget_enforcement.py # Budget enforcement
│   ├── test_jobs_api.py        # Job CRUD endpoints
│   ├── test_templates_api.py   # Template CRUD endpoints
│   ├── test_seed_data_api.py   # Seed data upload
│   ├── test_dashboard_api.py   # Dashboard statistics
│   ├── test_auth_flow.py       # Authentication flow
│   └── test_cors.py            # CORS configuration
│
├── e2e/                        # End-to-end tests (requires deployed app)
│   ├── test_complete_workflow.spec.ts   # Full user journey
│   ├── test_template_creation.spec.ts   # Template management
│   └── test_job_management.spec.ts      # Job operations
│
├── performance/                # Performance tests (load testing)
│   ├── locustfile.py           # Locust load test scenarios
│   └── README.md               # Performance testing guide
│
└── fixtures/                   # Shared test data and fixtures
```

## Test Types

### Unit Tests

**Purpose**: Test individual functions and classes in isolation

**Characteristics**:
- Fast (<30 seconds for full suite)
- No external dependencies
- Uses mocks for AWS services
- High coverage (>80% target)

**Run**: `pytest tests/unit/ -v`

**Coverage**: `pytest tests/unit/ --cov=backend --cov-report=html`

### Integration Tests

**Purpose**: Test component interactions with mocked AWS services

**Characteristics**:
- Uses `moto` to mock AWS services (DynamoDB, S3, etc.)
- Tests API endpoint behavior
- Tests worker job processing
- Tests database operations

**Run**: `pytest tests/integration/ -v`

**Note**: These tests use mocked AWS services, not real infrastructure.

### E2E Tests

**Purpose**: Test complete user workflows in a real browser

**Characteristics**:
- Uses Playwright for browser automation
- Tests across Chrome, Firefox, Safari
- Captures screenshots/videos on failure
- Requires deployed frontend

**Run**: `npx playwright test`

**Run in headed mode**: `npx playwright test --headed`

**Note**: Requires `FRONTEND_URL` environment variable for deployed app.

### Performance Tests

**Purpose**: Benchmark API performance under load

**Characteristics**:
- Uses Locust for load generation
- Simulates concurrent users
- Measures response times (p50, p95, p99)
- Tests throughput (req/sec)

**Run**: `locust -f tests/performance/locustfile.py --host=$API_ENDPOINT`

**Note**: Requires deployed API infrastructure.

## Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = --cov=backend --cov-report=html --cov-report=term-missing
```

### .coveragerc

```ini
[run]
source = backend
omit = */tests/*, */__init__.py

[report]
fail_under = 80
exclude_lines =
    pragma: no cover
    if __name__ == .__main__.:
```

### Pytest Markers

```python
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

## Environment Variables

### For Integration Tests

```bash
# AWS credentials (for real infrastructure tests in Phase 9)
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1

# DynamoDB table names
export JOBS_TABLE_NAME=test-Jobs
export QUEUE_TABLE_NAME=test-Queue
export TEMPLATES_TABLE_NAME=test-Templates
export COST_TRACKING_TABLE_NAME=test-CostTracking

# S3 bucket
export S3_BUCKET_NAME=test-bucket
```

### For E2E Tests

```bash
# Frontend URL
export FRONTEND_URL=http://localhost:5173

# Test user credentials
export TEST_USER_EMAIL=test@example.com
export TEST_USER_PASSWORD=TestPassword123!
```

### For Performance Tests

```bash
# API endpoint
export API_ENDPOINT=https://api.example.com
```

## Common Issues and Solutions

### ModuleNotFoundError: No module named 'backend'

**Problem**: Python can't find the backend package.

**Solution**: Install backend package in development mode:
```bash
pip install -e .
```

This installs the package so Python can find `backend.*` imports.

### ImportError: attempted relative import with no known parent package

**Problem**: Test file uses `sys.path.insert()` instead of proper imports.

**Solution**: Use imports like `from backend.shared.models import ...`

### Coverage below 80%

**Problem**: Test coverage is below the required threshold.

**Solution**: Check coverage report to see which files/lines are missing:
```bash
pytest tests/unit/ --cov=backend --cov-report=html
open htmlcov/index.html
```

Add tests for uncovered code paths.

### Integration tests fail with AWS errors

**Problem**: Tests try to connect to real AWS services.

**Solution**: Ensure tests use `moto` mocks:
```python
from moto import mock_dynamodb, mock_s3

@mock_dynamodb
@mock_s3
def test_something():
    # Test code here
```

### E2E tests can't find frontend

**Problem**: Playwright can't connect to frontend.

**Solution**:
1. Start frontend dev server: `cd frontend && npm run dev`
2. Set FRONTEND_URL: `export FRONTEND_URL=http://localhost:5173`
3. Or configure playwright.config.ts webServer

### Performance tests show high latency

**Problem**: API response times exceed targets.

**Solution**:
1. Check if using correct endpoint (staging vs production)
2. Verify API Gateway is not throttling
3. Check Lambda cold starts
4. Review DynamoDB capacity

## CI/CD Integration

Tests run automatically in GitHub Actions:

### On Every PR
- Unit tests with coverage
- Frontend linting and type checking
- Code quality checks (Black, Ruff, mypy)
- Security scanning (Trivy)

### On Deployment
- Pre-deployment unit tests
- Post-deployment smoke tests

### Scheduled (Daily)
- E2E tests against staging

### Manual Trigger
- Performance tests (configurable users/duration)

See `.github/workflows/` for workflow definitions.

## Best Practices

### Writing Unit Tests

```python
import pytest
from backend.shared.models import JobConfig

def test_job_config_validation():
    """Test that invalid budget raises ValueError."""
    with pytest.raises(ValueError, match="Budget must be positive"):
        JobConfig(
            job_id="test-123",
            user_id="user-456",
            budget_limit=-10  # Invalid
        )
```

### Writing Integration Tests

```python
import pytest
from moto import mock_dynamodb
import boto3

@pytest.fixture
def dynamodb_tables():
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        # Create tables
        yield dynamodb
        # Cleanup automatic with context manager

def test_job_creation(dynamodb_tables):
    # Test using mocked DynamoDB
    pass
```

### Writing E2E Tests

```typescript
import { test, expect } from '@playwright/test';

test('complete user workflow', async ({ page }) => {
  // Navigate to app
  await page.goto('/');

  // Fill form
  await page.fill('input[name="email"]', 'test@example.com');

  // Submit
  await page.click('button[type="submit"]');

  // Verify result
  await expect(page.locator('text=Success')).toBeVisible();
});
```

## Troubleshooting

### Tests pass locally but fail in CI

**Possible causes**:
1. Missing environment variables
2. Different Python/Node versions
3. Missing dependencies in CI

**Debug**:
1. Check GitHub Actions logs
2. Verify dependencies installed
3. Check environment variable setup

### Mocked AWS services behaving differently

**Possible causes**:
1. `moto` version mismatch
2. Incomplete mock setup

**Debug**:
1. Check moto version: `pip show moto`
2. Verify all required services are mocked
3. Check mock fixture scope (function vs session)

### Performance tests inconsistent results

**Possible causes**:
1. Network variability
2. Auto-scaling lag
3. Cold starts

**Solution**:
1. Run tests multiple times
2. Use longer test duration
3. Warm up services before testing

## Phase 8 vs Phase 9

**Phase 8 (Current - CODE WRITING ONLY)**:
- All test code written
- Tests use mocked AWS services (moto)
- No real infrastructure required
- No AWS costs incurred
- ✅ Can run: Unit tests, mocked integration tests
- ❌ Cannot run: E2E tests, performance tests (need deployed infrastructure)

**Phase 9 (DEPLOYMENT & VERIFICATION)**:
- Deploy actual AWS infrastructure
- Run integration tests against real services
- Execute E2E tests with deployed frontend
- Perform load testing with actual API
- Validate system end-to-end
- ✅ All tests can run

## Contributing

When adding new tests:

1. **Follow naming conventions**: `test_*.py` for test files
2. **Use appropriate markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
3. **Add docstrings**: Explain what the test validates
4. **Mock external services**: Never call real AWS services in unit/integration tests
5. **Keep tests fast**: Unit tests should run in <30 seconds total
6. **Maintain coverage**: Ensure coverage stays >80%

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [Playwright documentation](https://playwright.dev/)
- [Locust documentation](https://docs.locust.io/)
- [moto documentation](https://docs.getmoto.org/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
