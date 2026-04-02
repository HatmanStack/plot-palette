# Phase 0: Foundation

This phase defines architectural decisions, conventions, and testing strategies
that apply to all subsequent phases. No code changes are made in this phase.

## Architecture Decisions

### ADR-1: Fix in place, do not restructure

All fixes are applied to existing files in their current locations. No file moves,
no package restructuring. The `sys.path.insert` pattern in Lambda handlers is noted
as tech debt but is NOT addressed in this plan because it requires SAM packaging
changes that affect deployment infrastructure.

**Rationale:** The audit findings are about correctness, not structure. Restructuring
Lambda imports would require changes to `backend/template.yaml` packaging configuration
and deployment scripts, which is out of scope for a remediation plan.

### ADR-2: No new dependencies

All fixes use existing libraries (Pydantic, boto3, Jinja2, React). No new pip or
npm packages are introduced.

### ADR-3: Preserve backward compatibility

All DynamoDB schema changes (adding GSIs) are additive. No existing attributes or
key schemas change. API response shapes are preserved.

### ADR-4: Test coverage for every fix

Every code change must have a corresponding test that verifies the fix. Tests must
run without live AWS resources (use moto mocks for backend, vitest mocks for frontend).

## Tech Stack (no changes)

- **Backend:** Python 3.13, AWS Lambda, ECS Fargate, DynamoDB, S3, Step Functions
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS
- **Testing:** pytest + moto (backend), vitest + testing-library (frontend)
- **Linting:** Ruff (Python), ESLint (TypeScript), pre-commit hooks

## Testing Strategy

### Backend tests

- Location: `tests/` at repo root (NOT inside `backend/`)
- Run with: `PYTHONPATH=. pytest tests/unit/ -v` from repo root
- AWS mocking: `moto[all]` via fixtures in `tests/conftest.py`
- Environment: Set `AWS_DEFAULT_REGION=us-east-1` with dummy credentials
- Markers: `@pytest.mark.unit` for unit tests, `@pytest.mark.integration` for integration
- New test files follow pattern: `tests/unit/test_<module>.py`

### Frontend tests

- Location: `frontend/src/test/`
- Run with: `cd frontend && npx vitest run src/test/<file>.test.ts`
- Mocking: vitest `vi.mock()` for services, `@testing-library/react` for components

### Test patterns for this remediation

- For error handling fixes: test both the happy path AND the specific error condition
- For S3 error code fixes: mock `ClientError` with correct error code structure
- For DynamoDB fixes: use moto to create tables with GSIs, verify query behavior
- For frontend fixes: test timeout/error states with fake timers

## Commit Message Format

All commits use conventional commits:

```text
fix(scope): description of the fix

- Addresses health-audit finding CRITICAL-N / HIGH-N / etc.
- Brief explanation of what changed and why
```

Valid scopes for this remediation: `worker`, `lambda`, `shared`, `frontend`, `docs`, `docker`.

## Shared Patterns

### Error response pattern (Lambda handlers)

When fixing error handling in Lambda handlers, use the existing `error_response()`
and `success_response()` helpers from `backend/shared/lambda_responses.py`. Do not
create new response helpers.

### Logging pattern

Use structured JSON logging via the existing `setup_logger()` from `backend/shared/utils.py`.
Log with `json.dumps({...})` format that matches the existing codebase convention.

### DynamoDB error handling pattern

Always catch `ClientError` specifically, not bare `Exception`. Check
`e.response["Error"]["Code"]` for specific error codes.
