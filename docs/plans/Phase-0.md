# Phase 0: Foundation

## Phase Goal

Establish testing patterns, conventions, and shared utilities that all subsequent phases will follow. This phase creates the foundation for consistent, maintainable tests across frontend and backend.

**Success Criteria:**
- Test setup files configured for both frontend and backend
- Shared mock factories and test utilities created
- Testing conventions documented through example patterns
- CI pipeline verified to run all tests without AWS connectivity

**Estimated Tokens:** ~8,000

## Prerequisites

- Node.js v24+ installed
- Python 3.13+ installed
- Project dependencies installed (`npm install` in root and frontend)
- Backend dev dependencies installed (`uv pip install -r backend/requirements-dev.txt`)

---

## Architecture Decision Records

### ADR-001: Frontend Testing Framework

**Decision:** Use Vitest + React Testing Library + jest-dom

**Context:** The frontend already has Vitest configured with jsdom environment. React Testing Library encourages testing user behavior rather than implementation details.

**Consequences:**
- Tests focus on what users see and do, not component internals
- Mocking is straightforward via `vi.mock()`
- Compatible with existing Vite build setup

### ADR-002: Backend Testing Framework

**Decision:** Use pytest with moto for AWS service mocking

**Context:** pytest is already configured. moto provides drop-in replacements for boto3 clients that work without AWS credentials.

**Consequences:**
- All AWS operations (DynamoDB, S3, Bedrock, ECS, Cognito) are mocked
- Tests run in CI without AWS connectivity
- Existing test patterns in `tests/unit/` and `tests/integration/` are preserved

### ADR-003: Mocking Strategy

**Decision:** Moderate mocking - mock external services and heavy dependencies, but allow internal logic to execute.

**What to Mock:**
- AWS services (DynamoDB, S3, Bedrock, Cognito, ECS)
- Network requests (axios, fetch)
- Browser APIs when needed (localStorage, sessionStorage)
- Time-sensitive operations (dates, timers)

**What NOT to Mock:**
- Internal business logic
- Utility functions
- Data transformations
- React component rendering (test real DOM output)

### ADR-004: Test File Organization

**Decision:** Mirror source structure with `.test.ts` / `test_*.py` suffix

**Frontend:**
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
```

**Backend:**
```
tests/
├── unit/
│   ├── test_shared.py          # Existing
│   ├── test_lambda_handlers.py # New - Lambda error cases
│   └── test_worker_failures.py # New - Worker failure scenarios
```

---

## Tasks

### Task 1: Extend Frontend Test Setup

**Goal:** Extend the minimal test setup (currently 1 line: `import '@testing-library/jest-dom'`) to include common utilities and mock factories.

**Files to Create:**
- `frontend/src/test/setup.ts` - Extend existing minimal setup (add global mocks)
- `frontend/src/test/test-utils.tsx` - Create custom render with providers
- `frontend/src/test/mocks/auth.ts` - Create auth service mock factory
- `frontend/src/test/mocks/api.ts` - Create API service mock factory
- `frontend/src/test/mocks/react-query.tsx` - Create QueryClient wrapper

**Prerequisites:**
- None (first task)

**Implementation Steps:**

1. **Enhance setup.ts**
   - Add global mocks for `import.meta.env` variables
   - Mock `amazon-cognito-identity-js` module globally
   - Configure `afterEach` cleanup

2. **Create test-utils.tsx**
   - Export a custom `render` function that wraps components with:
     - `QueryClientProvider` (with test-configured client)
     - `BrowserRouter` (for routing context)
     - `AuthProvider` (optional, for authenticated scenarios)
   - Re-export everything from `@testing-library/react`

3. **Create auth mock factory**
   - Factory function that returns mock auth service functions
   - Configurable return values for `signIn`, `signUp`, `getIdToken`, `signOut`
   - Support for simulating auth errors

4. **Create API mock factory**
   - Factory function for mocking axios client
   - Configurable responses for each endpoint
   - Support for simulating network errors and timeouts

5. **Create QueryClient wrapper**
   - Pre-configured QueryClient with:
     - `retry: false` (no retries in tests)
     - `cacheTime: 0` (no caching between tests)
   - Wrapper component for easy test setup

**Verification Checklist:**
- [x] `npm test` runs without errors in frontend directory
- [x] Test utilities export correctly from `test-utils.tsx`
- [x] Mock factories can be imported and used
- [x] No console warnings about missing providers in tests

**Testing Instructions:**
- Write a simple smoke test that uses the custom render function
- Verify mocks can be configured per-test
- Run `npm test` to confirm setup works

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add test utilities and mock factories

- Enhance setup.ts with global mocks for env vars and Cognito
- Create custom render function with provider wrappers
- Add auth and API mock factories
- Configure QueryClient for testing
```

---

### Task 2: Create Backend Test Fixtures

**Goal:** Establish shared pytest fixtures for mocking AWS services consistently.

**Files to Create:**
- `tests/conftest.py` - Create root-level shared fixtures
- `tests/unit/conftest.py` - Create unit test specific fixtures
- `tests/fixtures/__init__.py` - Create package init
- `tests/fixtures/lambda_events.py` - Create API Gateway event factories
- `tests/fixtures/dynamodb_items.py` - Create DynamoDB item factories

**Prerequisites:**
- Phase 0 Task 1 complete
- Verify `backend/requirements-dev.txt` contains: `pytest`, `pytest-asyncio`, `pytest-cov`, `moto[all]`

**Implementation Steps:**

1. **Create root conftest.py**
   - Import and configure moto for AWS mocking
   - Create fixtures for mocked AWS clients:
     - `mock_dynamodb` - DynamoDB tables with proper schemas
     - `mock_s3` - S3 bucket with test data
     - `mock_bedrock` - Bedrock runtime mock
   - Set up environment variables fixture

2. **Create unit test conftest.py**
   - Import root fixtures
   - Add unit-test-specific fixtures:
     - `sample_job_config` - Valid job configuration
     - `sample_template` - Valid template definition
     - `sample_checkpoint` - Checkpoint state

3. **Create Lambda event factory**
   - Function to generate API Gateway v2 events
   - Support for:
     - Different HTTP methods (GET, POST, DELETE)
     - Path parameters
     - Query string parameters
     - Request body
     - Authorization claims (JWT)
   - Include realistic request context structure

4. **Create DynamoDB item factory**
   - Functions to create properly typed DynamoDB items:
     - `make_job_item(overrides)` - Job table item
     - `make_template_item(overrides)` - Template table item
     - `make_queue_item(overrides)` - Queue table item
     - `make_checkpoint_item(overrides)` - Checkpoint metadata item

**Verification Checklist:**
- [x] `pytest tests/unit -v` passes
- [x] Fixtures can be imported in test files
- [x] Lambda event factory produces valid event structures
- [x] DynamoDB item factory produces properly typed items
- [x] No AWS credentials required to run tests

**Testing Instructions:**
- Run existing unit tests to verify no regressions
- Import fixtures in a test file and verify they work
- Check moto mocks intercept AWS calls correctly

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add shared fixtures and mock factories

- Create root conftest.py with moto AWS mocks
- Add Lambda event factory for API Gateway events
- Add DynamoDB item factories for typed items
- Configure unit test fixtures
```

---

### Task 3: Document Testing Conventions

**Goal:** Create a testing conventions reference that engineers can follow.

**Files to Modify/Create:**
- `docs/testing-conventions.md` - Testing conventions document

**Prerequisites:**
- Tasks 1 and 2 (patterns established)

**Implementation Steps:**

1. **Document test file naming**
   - Frontend: `*.test.ts` or `*.test.tsx` co-located with source
   - Backend: `test_*.py` in appropriate `tests/` subdirectory

2. **Document test structure**
   - Describe-It pattern for frontend (via Vitest)
   - Class-based grouping for backend (pytest)
   - AAA pattern: Arrange, Act, Assert

3. **Document mocking patterns**
   - When to use `vi.mock()` vs `vi.spyOn()`
   - When to use moto vs manual mocking
   - How to reset mocks between tests

4. **Document assertion patterns**
   - Prefer specific assertions over generic
   - Use jest-dom matchers for DOM assertions
   - Use pytest assertions with descriptive messages

5. **Document common gotchas**
   - Async testing (waitFor, findBy queries)
   - Cleaning up after tests
   - Avoiding test interdependence

**Verification Checklist:**
- [ ] Document exists at `docs/testing-conventions.md`
- [ ] All code examples are syntactically correct
- [ ] Covers both frontend and backend patterns
- [ ] References actual project files and patterns

**Testing Instructions:**
- Review document for completeness
- Verify code examples match actual project patterns

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

docs: add testing conventions guide

- Document test file naming and structure
- Add mocking patterns for frontend and backend
- Include common gotchas and best practices
```

---

## Phase Verification

**How to verify Phase 0 is complete:**

1. **Frontend test infrastructure:**
   ```bash
   cd frontend && npm test
   ```
   - Should run without errors
   - Test utilities should be importable

2. **Backend test infrastructure:**
   ```bash
   PYTHONPATH=. pytest tests/unit -v
   ```
   - Should run without errors
   - No AWS credentials required

3. **Documentation:**
   - `docs/testing-conventions.md` exists and is comprehensive

**Integration Points:**
- Phase 1 will import from `frontend/src/test/test-utils.tsx`
- Phase 2 will import fixtures from `tests/conftest.py`

**Known Limitations:**
- Bedrock mocking is limited (moto has partial support)
- Some Cognito flows may need manual mocking

**Technical Debt:**
- None introduced in this phase
