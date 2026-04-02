# Phase 4: [FORTIFIER] Type Safety and Defensive Coding

## Phase Goal

Harden the codebase with improved type safety, defensive error handling patterns,
and guardrails that prevent regressions. This phase addresses the Defensiveness
(6/10) and Type Rigor (8/10) evaluation scores.

**Success criteria:** Bare `except Exception` replaced with typed catches in Lambda
handlers, idempotency race condition fixed, circuit breaker usage expanded, API
fetch error handling improved.

**Estimated tokens:** ~15,000

## Prerequisites

- Phase 3 complete (performance and architecture improvements in place)
- All tests passing

## Tasks

### Task 1: Replace bare except Exception in create_job handler

**Goal:** The create_job handler uses bare `except Exception` that swallows all
errors indiscriminately, losing context on auth failures and type errors. Replace
with typed exception catches.

**Source:** Eval defensiveness, Eval stress CRITICAL-2

**Files to Modify:**

- `backend/lambdas/jobs/create_job.py` -- Replace bare except with typed catches

**Prerequisites:**

- Read `create_job.py` lines 355-360 to see the bare except
- Identify the specific exception types that can occur in the try block

**Implementation Steps:**

- Replace `except Exception as e` with specific catches:
  - `ClientError` for AWS service errors (return 500 with service context)
  - `KeyError` for missing event fields (return 400)
  - `ValueError` for validation failures (return 400)
  - `json.JSONDecodeError` for malformed request body (return 400)
- Keep a final `except Exception` as a safety net, but log it at ERROR level with
  full traceback and the exception class name
- Each catch should return an appropriate HTTP status code and descriptive message

**Verification Checklist:**

- [x] No bare `except Exception` without logging
- [x] AWS errors return 500 with sanitized error
- [x] Client errors (KeyError, ValueError, JSONDecodeError) return 400
- [x] Safety net except logs full traceback at ERROR level
- [x] Test covers each exception type

**Testing Instructions:**

- Write tests in `tests/unit/test_create_job.py`:
  1. Test with malformed JSON body: verify 400 response
  1. Test with missing required fields: verify 400 response
  1. Test with DynamoDB ClientError: verify 500 with sanitized message
- Run: `PYTHONPATH=. pytest tests/unit/test_create_job.py -v`

**Commit Message Template:**

```text
fix(lambda): replace bare except with typed catches in create_job

- Addresses eval defensiveness target
- Auth failures and type errors now return appropriate status codes
```

---

### Task 2: Fix idempotency race condition in create_job

**Goal:** The idempotency check queries for an existing token but does not prevent
concurrent requests from creating duplicates between the check and the insert.
Use a DynamoDB ConditionExpression to make the check atomic.

**Source:** Eval stress CRITICAL-1, Health audit HIGH-9

**Files to Modify:**

- `backend/lambdas/jobs/create_job.py` -- Add ConditionExpression to put_item

**Prerequisites:**

- Read `create_job.py` lines 170-204 to understand the current idempotency flow
- Understand DynamoDB conditional writes

**Implementation Steps:**

- Instead of query-then-put, use `put_item` with a `ConditionExpression`:
  `attribute_not_exists(job_id)` to prevent overwrites
- If the condition fails (ConditionalCheckFailedException), the job already exists --
  return the existing job ID
- Remove the separate idempotency token query since the conditional write handles
  the race condition atomically
- If the idempotency token is stored separately from the job record, consider using
  `TransactWriteItems` to write both atomically

**Verification Checklist:**

- [x] put_item uses ConditionExpression
- [x] Duplicate creation attempt returns existing job (not error)
- [x] No separate query-then-put pattern remains
- [x] Test verifies concurrent creation returns same job

**Testing Instructions:**

- Write tests in `tests/unit/test_create_job.py`:
  1. Create a job with an idempotency token
  1. Attempt to create another job with the same token
  1. Verify the second attempt returns the first job's ID (not a new job)
- Run: `PYTHONPATH=. pytest tests/unit/test_create_job.py -v`

**Commit Message Template:**

```text
fix(lambda): use conditional write for atomic idempotency in create_job

- Addresses health-audit HIGH-9 and eval stress CRITICAL-1
- Eliminates race condition between idempotency check and insert
```

---

### Task 3: Expand circuit breaker usage to all Bedrock calls

**Goal:** The circuit breaker in `retry.py` is well-implemented but only used
where `circuit_breaker_name` is explicitly passed. Most Bedrock calls bypass it.
Ensure all Bedrock calls use the circuit breaker.

**Source:** Health audit CRITICAL-4

**Files to Modify:**

- `backend/ecs_tasks/worker/worker.py` -- Add circuit breaker to Bedrock calls
- `backend/lambdas/templates/test_template.py` -- Add circuit breaker to template test

**Prerequisites:**

- Read `backend/shared/retry.py` lines 195-243 to understand the circuit breaker API
- Search for all Bedrock `invoke_model` calls in the codebase

**Implementation Steps:**

- Find all places where Bedrock is called (search for `invoke_model` or
  `bedrock_runtime`)
- Ensure each call site passes `circuit_breaker_name="bedrock"` (or a more
  specific name like `"bedrock-us-east-1"`)
- In the worker, the generation loop should use the circuit breaker decorator or
  pass the parameter to the retry function
- If the circuit breaker is open, fail fast and mark the job as FAILED with a
  clear "Bedrock service unavailable" message

**Verification Checklist:**

- [x] All Bedrock invoke_model calls use circuit breaker
- [x] Circuit breaker open state causes fast failure
- [x] Job marked FAILED when circuit breaker is open
- [x] Test verifies circuit breaker triggers on repeated failures

**Testing Instructions:**

- Write tests in `tests/unit/test_worker.py`:
  1. Mock Bedrock to fail repeatedly
  1. Verify circuit breaker opens after threshold
  1. Verify subsequent calls fail fast without calling Bedrock
- Run: `PYTHONPATH=. pytest tests/unit/test_worker.py -v`

**Commit Message Template:**

```text
fix(worker): apply circuit breaker to all Bedrock calls

- Addresses health-audit CRITICAL-4
- Prevents cascade failures during Bedrock region outages
```

---

### Task 4: Improve frontend fetch error handling

**Goal:** The `fetch()` wrapper in `api.ts` only handles `!response.ok` but not
network errors (timeout, DNS failure, CORS pre-flight failure). These throw
different exceptions that are not caught.

**Source:** Health audit MEDIUM-15

**Files to Modify:**

- `frontend/src/services/api.ts` -- Add network error handling

**Prerequisites:**

- Read `api.ts` lines 37-56 to understand the current error handling

**Implementation Steps:**

- Wrap the `fetch()` call in a try/catch that handles:
  - `TypeError` -- network error (no connection, CORS failure)
  - `AbortError` -- request was aborted (timeout)
  - `DOMException` -- various browser-level errors
- Convert these to a consistent error format that the UI can display
- Distinguish between "server error" (response received, status >= 400) and
  "network error" (no response received at all)

**Verification Checklist:**

- [x] Network errors are caught and converted to consistent format
- [x] CORS failures produce a user-friendly error message
- [x] Timeouts produce a user-friendly error message
- [x] Test covers network error scenario

**Testing Instructions:**

- Write a test in `frontend/src/test/services/api.test.ts` (or extend):
  1. Mock fetch to throw TypeError (network error)
  1. Verify the error is caught and wrapped with a descriptive message
- Run: `cd frontend && npx vitest run src/test/services/api.test.ts`

**Commit Message Template:**

```text
fix(frontend): handle network errors in fetch wrapper

- Addresses health-audit MEDIUM-15
- Catches TypeError, AbortError for network/timeout failures
```

---

### Task 5: Fix stream_progress Decimal type handling

**Goal:** Cost and budget values in stream_progress are retrieved from DynamoDB
as Decimal/string types with ad-hoc `hasattr` type checks. Standardize the
conversion pattern.

**Source:** Health audit MEDIUM-14, HIGH-5 (related pattern)

**Files to Modify:**

- `backend/lambdas/jobs/stream_progress.py` -- Fix Decimal handling

**Prerequisites:**

- Read `stream_progress.py` lines 102-109

**Implementation Steps:**

- Replace ad-hoc `hasattr` checks with explicit `Decimal` to `float` conversion
- Create a small helper or use inline conversion: `float(value) if value else 0.0`
- Use `default=str` in the response serialization as a safety net
- Follow the same pattern applied in Phase 2 Task 8 (list_jobs)

**Verification Checklist:**

- [x] No `hasattr` checks for type detection
- [x] Decimal values explicitly converted to float
- [x] Response serialization uses default=str
- [x] Test verifies Decimal values serialize correctly

**Testing Instructions:**

- Write a test in `tests/unit/test_stream_progress.py`:
  1. Mock DynamoDB response with Decimal cost values
  1. Verify response contains valid float values
- Run: `PYTHONPATH=. pytest tests/unit/test_stream_progress.py -v`

**Commit Message Template:**

```text
fix(lambda): standardize Decimal handling in stream_progress

- Addresses health-audit MEDIUM-14
- Replaces ad-hoc hasattr checks with explicit conversion
```

---

### Task 6: Add error sanitization for AWS ARNs

**Goal:** The error sanitization regex in `utils.py` does not fully handle AWS ARN
format, potentially leaking resource IDs in error messages.

**Source:** Health audit MEDIUM-11

**Files to Modify:**

- `backend/shared/utils.py` -- Improve ARN sanitization regex

**Prerequisites:**

- Read `utils.py` lines 94-132 to understand the current sanitization

**Implementation Steps:**

- Update the ARN regex pattern to match the full ARN format:
  `arn:aws[a-zA-Z-]*:[a-zA-Z0-9-]+:[a-zA-Z0-9-]*:\d{12}:[a-zA-Z0-9/_.-]+`
- Replace matched ARNs with `arn:aws:***:***:***:***` (fully redacted)
- Test with various ARN formats: Lambda ARN, S3 ARN, DynamoDB table ARN, role ARN

**Verification Checklist:**

- [x] Full ARN format matched by regex
- [x] ARNs with resource paths (e.g., `role/my-role`) are fully redacted
- [x] Test covers multiple ARN formats

**Testing Instructions:**

- Write tests in `tests/unit/test_utils.py` (or extend):
  1. Pass error message containing a Lambda function ARN
  1. Pass error message containing a role ARN with path
  1. Pass error message containing a DynamoDB table ARN
  1. Verify all are fully redacted
- Run: `PYTHONPATH=. pytest tests/unit/test_utils.py -v`

**Commit Message Template:**

```text
fix(shared): improve ARN sanitization in error messages

- Addresses health-audit MEDIUM-11
- Handles all ARN formats including resource paths
```

## Phase Verification

- All backend tests pass: `PYTHONPATH=. pytest tests/ -v`
- All frontend tests pass: `cd frontend && npx vitest run`
- Linting passes: `npm run lint && npm run lint:backend`
- No bare `except Exception` in create_job.py
- All Bedrock calls use circuit breaker
- Idempotency is atomic (no query-then-put)
- Frontend handles network errors gracefully
