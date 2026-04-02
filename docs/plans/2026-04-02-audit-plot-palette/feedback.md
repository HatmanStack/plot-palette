# Feedback Log

## Active Feedback

### PLAN_REVIEW (2026-04-02)

#### Suggestions

1. **Test file naming mismatch (Phase 1 Task 3, Phase 2 Task 4)**: Plan instructs writing tests in `tests/unit/test_lambda_responses.py`, but the existing test file for `lambda_responses.py` is `tests/unit/test_responses.py`. A zero-context engineer would create a second file, leading to duplicate test infrastructure. Change references to `tests/unit/test_responses.py` (or extend existing).

1. **Worker test file naming mismatch (Phase 2 Tasks 3/7, Phase 3 Tasks 3/4, Phase 4 Task 3)**: Plan instructs writing tests in `tests/unit/test_worker.py`, but no such file exists. Worker tests are split across six files: `test_worker_s3_errors.py`, `test_worker_bedrock_errors.py`, `test_worker_budget.py`, `test_worker_dynamodb_errors.py`, `test_worker_export.py`, `test_worker_spot_interruption.py`. The implementer should extend the relevant existing file (e.g., budget tests go in `test_worker_budget.py`, Bedrock error tests go in `test_worker_bedrock_errors.py`) rather than creating a monolithic `test_worker.py`.

1. **Utils test file naming mismatch (Phase 4 Task 6)**: Plan says `tests/unit/test_utils.py` but the existing file is `tests/unit/test_utils_extended.py`. Change reference to match or extend the existing file.

1. **Frontend test subdirectories do not exist**: Plan references `frontend/src/test/services/api.test.ts`, `frontend/src/test/contexts/AuthContext.test.tsx`, and `frontend/src/test/hooks/useJobPolling.test.tsx` -- the `services/`, `contexts/`, and `hooks/` subdirectories under `frontend/src/test/` do not exist. The plan should note these directories need to be created, or the implementer should place tests in the flat `frontend/src/test/` directory following the existing `smoke.test.tsx` pattern.

### CODE_REVIEW Phase 2 (2026-04-02)

#### Issues

1. **Task 4 (CORS) test exists but in a different file than spec**: The plan spec said to create `tests/unit/test_lambda_responses.py`, but the test was correctly placed in the existing `tests/unit/test_responses.py` (following the PLAN_REVIEW suggestion). This is the right call, just noting for traceability.

#### Observations (non-blocking)

1. **All 10 source code changes are correct and match their specifications**: stream_progress error handling, create_job cascading failure with ConditionExpression, worker cost tracking placement, CORS error log level, frontend auth error propagation, AuthContext timeout, standalone mode exit handling, list_jobs Decimal serialization, missing template ValueError, and Jinja2 render timeout via threading are all implemented as designed.

1. **Commit messages follow conventional commits format and reference audit findings**: All 10 commits plus the docs commit use correct scopes and format.

1. **Build, lint, and all tests pass**: 106 backend tests pass, 5 frontend tests pass, ESLint and Ruff are clean, Vite build succeeds.

1. **Template render timeout uses threading.Thread instead of signal.alarm**: This avoids conflicting with the existing SIGALRM handler in worker.py, which is the right design choice per the spec.

## Resolved Feedback

### CODE_REVIEW Phase 2 — Worker tests (2026-04-02)

1. **Worker tests for Tasks 3 and 7 are behavioral simulations, not integration tests** — RESOLVED: Added `TestBedrockCostOnFailureIntegration` (in `test_worker_bedrock_errors.py`) and `TestStandaloneModeExitRaceIntegration` (in `test_worker_dynamodb_errors.py`). These tests instantiate the actual `Worker` class with mocked dependencies and exercise the real `generate_data` and `process_job` code paths, verifying that `running_cost` is not incremented on failed records and that `mark_job_failed` is called when `process_job` catches an exception. Commit: `test(worker): improve worker integration tests for cost tracking and failure handling`.
