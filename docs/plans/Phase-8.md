# Phase 8: Integration Testing & End-to-End Testing

## Phase Goal

Create comprehensive test suites covering unit tests, integration tests, and end-to-end tests to ensure system reliability and catch regressions. By the end of this phase, all critical paths are tested and CI/CD pipeline runs tests automatically.

**Success Criteria:**
- Unit test coverage > 80% for business logic
- Integration tests for all API endpoints
- End-to-end tests for critical user workflows
- Performance tests for API and worker
- Load tests for concurrent job processing
- CI/CD pipeline configured with GitHub Actions
- Test reports and coverage dashboards

**Estimated Tokens:** ~75,000

---

## Prerequisites

- **Phases 1-7** completed (full system deployed)
- pytest and testing libraries installed
- Understanding of testing strategies

---

## Task 1: Unit Test Suite

### Goal

Comprehensive unit tests for backend logic (shared library, Lambda functions, worker) with >80% coverage.

### Files to Create

- `tests/unit/test_models.py` - Data model validation tests
- `tests/unit/test_utils.py` - Utility function tests
- `tests/unit/test_template_engine.py` - Jinja2 template rendering tests
- `tests/unit/test_filters.py` - Custom filter tests
- `tests/unit/test_cost_calculation.py` - Cost tracking logic tests
- `pytest.ini` - Pytest configuration
- `.coveragerc` - Coverage configuration

### Prerequisites

- Backend code from Phases 3-5 complete
- Understanding of pytest and mocking
- AWS SDK mocking with moto or boto3 stubs

### Implementation Steps

1. **Install testing dependencies:**
   ```bash
   pip install pytest pytest-cov pytest-asyncio moto boto3-stubs
   ```

2. **Configure pytest** (`pytest.ini`):
   ```ini
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = --cov=backend --cov-report=html --cov-report=term-missing
   ```

3. **Test models** - Focus on:
   - JobRequest validation (required fields, budget limits)
   - TemplateDefinition schema validation
   - SeedData parsing and format detection
   - JobStatus state transitions
   - Enum validation

**Example pattern:**
```python
def test_job_request_validates_budget():
    with pytest.raises(ValueError, match="Budget must be positive"):
        JobRequest(budget_limit=-10, ...)

def test_template_definition_requires_prompt():
    with pytest.raises(ValueError):
        TemplateDefinition(name="test")  # Missing prompt
```

4. **Test template engine** - Focus on:
   - Template compilation
   - Variable substitution from seed data
   - Custom filter execution
   - Conditional rendering
   - Error handling for invalid templates

5. **Test cost calculation** - Focus on:
   - Token counting (input + output)
   - Cost per model (Bedrock pricing)
   - Budget enforcement
   - Cumulative cost tracking

6. **Mock AWS services:**
   - Use `moto` for DynamoDB, S3, Bedrock mocks
   - Use `pytest.fixture` for reusable mocks
   - Mock environment variables

### Verification Checklist

- [ ] All unit tests pass
- [ ] Coverage >80% for business logic
- [ ] Tests run in <30 seconds
- [ ] Mocks used for AWS services
- [ ] Edge cases tested (empty data, invalid input)
- [ ] Error handling tested

### Testing Instructions

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=backend --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py -v

# Open coverage report
open htmlcov/index.html
```

### Commit Message Template

```
test(backend): add comprehensive unit test suite

- Add unit tests for models, utils, template engine
- Test custom filters and cost calculation
- Configure pytest with coverage reporting
- Mock AWS services with moto
- Achieve >80% code coverage

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 2: API Integration Tests

### Goal

Test all API endpoints with real AWS services in isolated test environment.

### Files to Create

- `tests/integration/test_api_auth.py` - Authentication tests
- `tests/integration/test_api_jobs.py` - Job CRUD tests
- `tests/integration/test_api_templates.py` - Template CRUD tests
- `tests/integration/test_api_seed_data.py` - Seed data upload tests
- `tests/integration/conftest.py` - Shared fixtures
- `infrastructure/cloudformation/test-stack.yaml` - Test environment stack

### Prerequisites

- Phase 3 completed (all APIs implemented)
- AWS test account or isolated test environment
- Understanding of pytest fixtures

### Implementation Steps

1. **Create test environment stack** - Minimal version of production:
   - Single DynamoDB table with test prefix
   - Test S3 bucket with auto-delete policy
   - Test Cognito User Pool
   - Lambda functions in test mode
   - Mock Bedrock (no real API calls)

2. **Configure test fixtures** (`conftest.py`):
   ```python
   @pytest.fixture(scope="session")
   def api_client():
       """HTTP client for API Gateway"""
       return boto3.client('apigatewayv2', region_name='us-east-1')

   @pytest.fixture(scope="function")
   def test_user():
       """Create and cleanup test user"""
       # Create user, yield credentials, delete after test

   @pytest.fixture(scope="function")
   def auth_token(test_user):
       """Get valid JWT token for test user"""
       # Login and return token
   ```

3. **Test authentication endpoints:**
   - POST /signup - User registration
   - POST /login - User login with valid credentials
   - POST /login - Reject invalid credentials
   - GET /user - Get current user (authenticated)
   - Token expiration and refresh

4. **Test job CRUD endpoints:**
   - POST /jobs - Create job with valid data
   - POST /jobs - Reject invalid budget
   - GET /jobs - List user's jobs
   - GET /jobs/{id} - Get specific job
   - DELETE /jobs/{id} - Delete job
   - PATCH /jobs/{id} - Update job status

5. **Test template CRUD:**
   - POST /templates - Create template
   - GET /templates - List templates (system + user)
   - PUT /templates/{id} - Update template
   - POST /templates/{id}/test - Test template rendering

6. **Test seed data upload:**
   - POST /jobs/{id}/seed-data - Upload CSV
   - POST /jobs/{id}/seed-data - Upload JSONL
   - Reject invalid formats
   - Check S3 storage

7. **Cleanup strategy:**
   - Use fixtures with teardown
   - Delete test data after each test
   - Clear S3 buckets
   - Remove test users

### Verification Checklist

- [ ] All API endpoints tested
- [ ] Authentication and authorization tested
- [ ] Error responses validated (400, 401, 404, 500)
- [ ] Test environment isolated from production
- [ ] Fixtures cleanup after tests
- [ ] Mock Bedrock to avoid costs

### Testing Instructions

```bash
# Deploy test environment
aws cloudformation create-stack \
    --stack-name plot-palette-test \
    --template-body file://infrastructure/cloudformation/test-stack.yaml

# Set test environment variables
export API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name plot-palette-test --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)

# Run integration tests
pytest tests/integration/ -v --integration

# Cleanup test environment
aws cloudformation delete-stack --stack-name plot-palette-test
```

### Commit Message Template

```
test(api): add integration tests for all API endpoints

- Test authentication, job CRUD, template CRUD
- Create isolated test environment with CloudFormation
- Add pytest fixtures for user creation and cleanup
- Mock Bedrock to avoid costs during testing
- Test error handling and edge cases

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Task 3: Worker Integration Tests

### Goal

Test ECS worker logic with small Bedrock jobs to validate generation, checkpointing, and budget enforcement.

### Files to Create

- `tests/integration/test_worker.py` - Worker tests
- `tests/integration/test_checkpoint.py` - Checkpoint tests
- `tests/integration/test_budget_enforcement.py` - Budget limit tests

### Prerequisites

- Phase 4 completed (ECS worker)
- Test AWS account with Bedrock access
- Small test budget ($0.50-$1.00)

### Implementation Steps

1. **Test job queue processing:**
   - Create job in DynamoDB JobQueue table
   - Launch ECS task with test configuration
   - Verify task picks up job and updates status to RUNNING
   - Monitor CloudWatch logs for progress

2. **Test data generation (small job):**
   - Use simple template and 10 seed records
   - Generate with cheap model (Llama 3.1 8B)
   - Verify generated data saved to S3
   - Check cost tracking in CostTracking table

3. **Test checkpoint save/load:**
   - Create job with 100 records
   - Force checkpoint at 50 records (modify CHECKPOINT_INTERVAL)
   - Kill ECS task
   - Restart job, verify it resumes from checkpoint 50

4. **Test budget enforcement:**
   - Create job with $0.10 budget limit
   - Run generation until budget exceeded
   - Verify job stops with BUDGET_EXCEEDED status
   - Check no charges beyond budget

5. **Test spot interruption handling:**
   - Simulate spot interruption signal
   - Verify checkpoint saved before termination
   - Verify job can resume from checkpoint

6. **Test export functionality:**
   - Complete job with 50 records
   - Export to JSONL, CSV, Parquet
   - Download and validate format

### Verification Checklist

- [ ] Worker processes jobs from queue
- [ ] Bedrock integration generates data
- [ ] Checkpoints save and restore correctly
- [ ] Budget limits enforced
- [ ] Spot interruptions handled gracefully
- [ ] Exports created in all formats

### Testing Instructions

```bash
# Run worker tests (requires AWS credentials and Bedrock access)
pytest tests/integration/test_worker.py -v --slow

# Test with specific budget
pytest tests/integration/test_budget_enforcement.py -v -k test_budget_exceeded

# View worker logs
aws logs tail /aws/ecs/plot-palette-worker --follow
```

### Commit Message Template

```
test(worker): add integration tests for ECS worker

- Test job queue processing and data generation
- Test checkpoint save/restore functionality
- Test budget enforcement with real Bedrock costs
- Test spot interruption handling
- Validate export functionality for all formats

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 4: End-to-End Tests

### Goal

Automated browser tests for complete user workflows using Playwright or Cypress.

### Files to Create

- `tests/e2e/test_complete_workflow.spec.ts` - Full user journey
- `tests/e2e/test_template_creation.spec.ts` - Template workflow
- `tests/e2e/test_job_management.spec.ts` - Job operations
- `playwright.config.ts` - Playwright configuration

### Prerequisites

- Phase 6 completed (frontend deployed)
- Frontend accessible via URL
- Test user credentials

### Implementation Steps

1. **Install Playwright:**
   ```bash
   npm install -D @playwright/test
   npx playwright install
   ```

2. **Configure Playwright:**
   ```typescript
   export default defineConfig({
     testDir: './tests/e2e',
     use: {
       baseURL: process.env.FRONTEND_URL,
       screenshot: 'only-on-failure',
       video: 'retain-on-failure',
     },
     projects: [
       { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
       { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
     ],
   })
   ```

3. **Test complete workflow:**
   - Navigate to signup page
   - Create new user account
   - Verify email (mock or manual)
   - Login with credentials
   - Navigate to templates page
   - Create new template with prompt
   - Upload seed data CSV
   - Create job with budget limit
   - Monitor progress (poll until complete)
   - Download export
   - Verify export file contents

4. **Test template creation and testing:**
   - Create template with variables
   - Test template with sample data
   - Verify preview renders correctly
   - Save template

5. **Test job management:**
   - Create multiple jobs
   - View job list on dashboard
   - Filter by status
   - Cancel running job
   - Delete completed job

6. **Test budget enforcement UI:**
   - Create job with low budget
   - Watch progress stop at budget limit
   - Verify UI shows BUDGET_EXCEEDED status

### Verification Checklist

- [ ] Complete workflow tested end-to-end
- [ ] Tests run in multiple browsers
- [ ] Screenshots captured on failure
- [ ] Authentication tested
- [ ] Job creation and monitoring tested
- [ ] Export download validated

### Testing Instructions

```bash
# Run E2E tests
npm run test:e2e

# Run in headed mode (see browser)
npm run test:e2e -- --headed

# Run specific test
npm run test:e2e -- test_complete_workflow.spec.ts

# View test report
npx playwright show-report
```

### Commit Message Template

```
test(e2e): add end-to-end tests for user workflows

- Test complete user journey with Playwright
- Test template creation and testing flow
- Test job creation, monitoring, and management
- Configure multi-browser testing
- Add screenshot and video recording on failure

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~13,000

---

## Task 5: Performance Testing and CI/CD Pipeline

### Goal

Benchmark API performance and set up GitHub Actions for automated testing.

### Files to Create

- `tests/performance/locustfile.py` - Load testing script
- `.github/workflows/test.yml` - CI/CD pipeline
- `.github/workflows/deploy.yml` - Deployment workflow

### Prerequisites

- All tests from Tasks 1-4 complete
- GitHub repository
- Understanding of GitHub Actions

### Implementation Steps

1. **Create load tests with Locust:**
   ```python
   from locust import HttpUser, task, between

   class APIUser(HttpUser):
       wait_time = between(1, 3)

       @task
       def list_jobs(self):
           self.client.get("/jobs", headers={"Authorization": f"Bearer {self.token}"})

       @task
       def create_job(self):
           self.client.post("/jobs", json={...})
   ```

2. **Run performance tests:**
   - Target: API latency <500ms (p95)
   - Concurrent users: 50
   - Duration: 5 minutes
   - Measure: requests/second, error rate

3. **Create CI/CD pipeline** (`.github/workflows/test.yml`):
   - Trigger on PR and push to main
   - Run unit tests
   - Run integration tests (if AWS credentials available)
   - Generate coverage report
   - Fail if coverage <80%

**Example workflow:**
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: pytest tests/unit/ --cov
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

4. **Create deployment workflow:**
   - Trigger on release tag
   - Deploy CloudFormation stacks
   - Run smoke tests
   - Notify on failure

### Verification Checklist

- [ ] Load tests execute successfully
- [ ] API meets performance targets
- [ ] CI/CD runs on every PR
- [ ] Tests pass before merge
- [ ] Coverage report generated
- [ ] Deployment workflow tested

### Testing Instructions

```bash
# Run load tests locally
pip install locust
locust -f tests/performance/locustfile.py --host=$API_ENDPOINT

# Trigger CI/CD (push to GitHub)
git push origin main

# View workflow results
# Check GitHub Actions tab
```

### Commit Message Template

```
test(perf): add performance tests and CI/CD pipeline

- Create Locust load tests for API endpoints
- Set up GitHub Actions for automated testing
- Add coverage reporting with Codecov
- Create deployment workflow for releases
- Document performance benchmarks

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~11,000

---

## Phase 8 Verification

**Success Criteria:**

- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests pass for all APIs
- [ ] Worker tests validate generation and checkpointing
- [ ] E2E tests pass for critical workflows
- [ ] Performance tests meet latency targets
- [ ] CI/CD pipeline runs on every PR
- [ ] Test reports and coverage generated
- [ ] All tests documented and reproducible

**Estimated Total Tokens:** ~62,000

---

**Navigation:**
- [← Previous: Phase 7](./Phase-7.md)
- [Next: Phase 9 - Documentation & Deployment →](./Phase-9.md)
