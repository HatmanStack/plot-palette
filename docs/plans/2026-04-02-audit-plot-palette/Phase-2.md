# Phase 2: [IMPLEMENTER] Critical Error Handling and Operational Fixes

## Phase Goal

Fix the most dangerous error handling gaps and operational issues identified in the
health audit CRITICAL and HIGH findings. These are bugs that cause data corruption,
silent failures, or user-facing 500 errors.

**Success criteria:** All CRITICAL error handling issues fixed, HIGH-priority error
handling issues fixed, each fix covered by at least one test.

**Estimated tokens:** ~25,000

## Prerequisites

- Phase 1 complete (dead code removed, quick wins applied)
- All tests passing before starting

## Tasks

### Task 1: Fix stream_progress Lambda error handling

**Goal:** The stream_progress handler lacks top-level try/except for DynamoDB calls
and does not catch missing `pathParameters` or JWT auth info, causing unhandled
KeyError and 500 responses.

**Source:** Health audit CRITICAL-3

**Files to Modify:**

- `backend/lambdas/jobs/stream_progress.py` -- Add error handling for missing keys

**Prerequisites:**

- Read the full file to understand the handler structure
- Note the existing imports of `error_response` from `lambda_responses`

**Implementation Steps:**

- Wrap the extraction of `pathParameters` and JWT claims in a try/except KeyError
  block that returns a 400 error response
- Add a top-level try/except around the DynamoDB `get_item` call that returns a 500
  error response with logging
- Follow the same pattern used in other Lambda handlers (e.g., `download_job.py`)
- Ensure the handler returns appropriate error responses for: missing pathParameters,
  missing job_id in pathParameters, missing JWT claims, DynamoDB errors

**Verification Checklist:**

- [x] Missing `pathParameters` returns 400, not 500
- [x] Missing `job_id` in pathParameters returns 400, not 500
- [x] Missing JWT claims returns 401, not 500
- [x] DynamoDB errors return 500 with logging (not unhandled)
- [x] Happy path still works

**Testing Instructions:**

- Write tests in `tests/unit/test_stream_progress.py` (create if needed):
  1. Test with event missing `pathParameters` key entirely
  1. Test with event missing `requestContext.authorizer.jwt.claims.sub`
  1. Test happy path with valid event and mocked DynamoDB response
- Run: `PYTHONPATH=. pytest tests/unit/test_stream_progress.py -v`

**Commit Message Template:**

```text
fix(lambda): add error handling for missing keys in stream_progress

- Addresses health-audit CRITICAL-3
- Missing pathParameters or JWT claims now return 400/401 instead of 500
```

---

### Task 2: Fix create_job cascading failure on SFN error

**Goal:** When Step Functions execution start fails, the code tries to update job
status to FAILED, but if that update also fails, the job is left in an inconsistent
QUEUED state with no execution ARN. Fix the error handling to ensure the job is
always cleaned up.

**Source:** Health audit CRITICAL-7

**Files to Modify:**

- `backend/lambdas/jobs/create_job.py` -- Fix error handling in SFN start section

**Prerequisites:**

- Read `create_job.py` lines 290-345 to understand the SFN error flow
- Understand the DynamoDB update pattern used elsewhere in the file

**Implementation Steps:**

- In the SFN error catch block (around line 302-341), if the DynamoDB status update
  to FAILED also fails, log the double failure with both error messages
- Return a 500 response that clearly states the job was created but may be in an
  inconsistent state, including the job_id so the client can retry or check status
- Consider using a DynamoDB `ConditionExpression` on the update to ensure we only
  update if the job is still in QUEUED status (prevent race with another process)

**Verification Checklist:**

- [x] SFN failure + DynamoDB update failure is logged with both errors
- [x] Response includes the job_id for client-side recovery
- [x] Job status update uses ConditionExpression to prevent stale updates
- [x] Test covers the double-failure scenario

**Testing Instructions:**

- Write tests in `tests/unit/test_create_job.py` (create if needed):
  1. Test SFN start failure: mock SFN to raise ClientError, verify job marked FAILED
  1. Test double failure: mock both SFN and DynamoDB update to fail, verify 500 response
     includes job_id
- Run: `PYTHONPATH=. pytest tests/unit/test_create_job.py -v`

**Commit Message Template:**

```text
fix(lambda): handle cascading SFN and DynamoDB failures in create_job

- Addresses health-audit CRITICAL-7
- Double failures now logged, response includes job_id for recovery
```

---

### Task 3: Fix worker silent failure on Bedrock errors

**Goal:** When Bedrock calls fail during the generation loop, the worker silently
continues and increments failed_records without rolling back cost tracking. Fix to
ensure failed calls do not count toward running cost.

**Source:** Health audit CRITICAL-8

**Files to Modify:**

- `backend/ecs_tasks/worker/worker.py` -- Fix cost tracking on Bedrock failure

**Prerequisites:**

- Read `worker.py` lines 310-380 to understand the generation loop
- Understand the cost tracking mechanism (where `cost_accumulated` is updated)

**Implementation Steps:**

- In the generation loop, move the cost accumulation to AFTER a successful Bedrock
  response (not before the call)
- When a Bedrock call fails, do NOT add to `cost_accumulated`
- Log the failure with the record index and error type (transient vs permanent)
- Keep the existing `failed_records` counter increment

**Verification Checklist:**

- [x] Cost is only accumulated after successful Bedrock responses
- [x] Failed Bedrock calls do not affect cost tracking
- [x] Failed records are still counted
- [x] Test verifies cost is not incremented on failure

**Testing Instructions:**

- Write tests in `tests/unit/test_worker.py` (create or extend):
  1. Test successful generation: verify cost_accumulated increases
  1. Test failed Bedrock call: verify cost_accumulated does NOT increase
  1. Test failed call: verify failed_records counter increments
- Run: `PYTHONPATH=. pytest tests/unit/test_worker.py -v`

**Commit Message Template:**

```text
fix(worker): only accumulate cost after successful Bedrock calls

- Addresses health-audit CRITICAL-8
- Failed Bedrock calls no longer inflate cost tracking
```

---

### Task 4: Fix CORS origin validation in lambda_responses

**Goal:** If `ALLOWED_ORIGIN` env var is not set, the CORS header defaults to the
string `"null"`, which will cause all frontend requests to fail. Add validation
that warns loudly and provides a sensible default.

**Source:** Health audit HIGH-8, Quick Win #4

**Files to Modify:**

- `backend/shared/lambda_responses.py` -- Improve ALLOWED_ORIGIN handling

**Implementation Steps:**

- The current code already logs a warning when `ALLOWED_ORIGIN` is not set. This is
  acceptable for Lambda (env vars are set via SAM template).
- Add a check: if `_allowed_origin == "null"`, log at ERROR level (not WARNING) to
  make it more visible in CloudWatch
- Change the log level from `warning` to `error` since this will break all requests

**Verification Checklist:**

- [x] Missing ALLOWED_ORIGIN logs at ERROR level
- [x] Existing behavior preserved (still defaults to "null")
- [x] Test verifies the error log is emitted

**Testing Instructions:**

- Write a test in `tests/unit/test_lambda_responses.py` that patches `os.environ`
  to remove `ALLOWED_ORIGIN` and verifies the error log is emitted
- Run: `PYTHONPATH=. pytest tests/unit/test_lambda_responses.py -v`

**Commit Message Template:**

```text
fix(shared): escalate CORS origin warning to error level

- Addresses health-audit HIGH-8
- Missing ALLOWED_ORIGIN now logs at ERROR for CloudWatch visibility
```

---

### Task 5: Fix frontend auth token silent downgrade

**Goal:** `getAuthHeaders()` catches errors globally and returns empty `{}`, silently
downgrading to an unauthenticated request. This causes redirect loops when the user
is logged in but token refresh fails.

**Source:** Health audit HIGH-1

**Files to Modify:**

- `frontend/src/services/api.ts` -- Fix auth header error handling

**Prerequisites:**

- Read `frontend/src/services/api.ts` lines 6-14 to understand current behavior
- Read `frontend/src/services/auth.ts` to understand what errors the token fetch can throw

**Implementation Steps:**

- Instead of returning empty `{}` on auth error, re-throw the error so the caller
  can handle it appropriately
- OR: return a sentinel that triggers a proper auth refresh flow instead of silently
  making an unauthenticated request
- The key insight: an unauthenticated request will get a 401, which triggers a login
  redirect, but the user IS logged in -- this creates a loop
- Recommended approach: let the error propagate and handle it in the API interceptor
  (response handler) by checking if the error is an auth error vs a network error

**Verification Checklist:**

- [x] Auth token fetch failure does not silently downgrade to unauthenticated request
- [x] Error propagates to caller for proper handling
- [x] Test covers the auth failure scenario

**Testing Instructions:**

- Write a test in `frontend/src/test/services/api.test.ts` (or extend existing):
  1. Mock auth service to throw an error
  1. Verify `getAuthHeaders()` throws (does not return empty object)
- Run: `cd frontend && npx vitest run src/test/services/api.test.ts`

**Commit Message Template:**

```text
fix(frontend): propagate auth token errors instead of silent downgrade

- Addresses health-audit HIGH-1
- Prevents redirect loop when token refresh fails
```

---

### Task 6: Fix AuthContext loading state timeout

**Goal:** If the auth service is offline, `checkAuth()` in the AuthContext hangs
forever, leaving the UI stuck in loading state. Add a timeout.

**Source:** Health audit HIGH-10, Quick Win #5

**Files to Modify:**

- `frontend/src/contexts/AuthContext.tsx` -- Add timeout to checkAuth

**Implementation Steps:**

- Wrap the `checkAuth()` call in `useEffect` with a timeout (e.g., 10 seconds)
- If the timeout fires before checkAuth resolves, set `loading` to false and
  `isAuthenticated` to false, allowing the user to reach the login page
- Use `Promise.race()` with a timeout promise
- Clean up the timeout on unmount

**Verification Checklist:**

- [x] Loading state resolves after timeout even if auth service is down
- [x] User can reach the login page after timeout
- [x] Successful auth check still works normally
- [x] Timeout is cleaned up on unmount

**Testing Instructions:**

- Write a test in `frontend/src/test/contexts/AuthContext.test.tsx` (or extend):
  1. Mock auth service to never resolve (return a promise that never settles)
  1. Use fake timers to advance past the timeout
  1. Verify loading becomes false
- Run: `cd frontend && npx vitest run src/test/contexts/AuthContext.test.tsx`

**Commit Message Template:**

```text
fix(frontend): add timeout to AuthContext checkAuth to prevent infinite loading

- Addresses health-audit HIGH-10
- UI no longer stuck if auth service is unreachable
```

---

### Task 7: Fix worker standalone mode async state update race

**Goal:** In standalone mode, `process_job` marks a job FAILED but the caller
exits before the DynamoDB update completes, leaving the job stuck in QUEUED status.

**Source:** Health audit HIGH-4

**Files to Modify:**

- `backend/ecs_tasks/worker/worker.py` -- Ensure DynamoDB update completes before exit

**Prerequisites:**

- Read `worker.py` lines 148-162 (`_run_standalone_mode`) and lines 254-271
  (`process_job` exception handling)

**Implementation Steps:**

- In `_run_standalone_mode`, ensure the process waits for the status update to
  complete before returning/exiting
- If `process_job` raises, catch the exception, perform the FAILED status update,
  and wait for it to complete before re-raising or exiting
- Use a try/finally pattern to guarantee the update happens

**Verification Checklist:**

- [x] Status update to FAILED completes before process exits
- [x] Test verifies DynamoDB update is called before exit

**Testing Instructions:**

- Write a test in `tests/unit/test_worker.py`:
  1. Mock `process_job` to raise an exception
  1. Verify the DynamoDB update_item call completes before the method returns
- Run: `PYTHONPATH=. pytest tests/unit/test_worker.py -v`

**Commit Message Template:**

```text
fix(worker): ensure DynamoDB status update completes before exit

- Addresses health-audit HIGH-4
- Prevents jobs stuck in QUEUED state after standalone mode failures
```

---

### Task 8: Fix list_jobs Decimal/float serialization

**Goal:** Cost and budget values from DynamoDB are Decimal types. The conversion
logic is inconsistent, causing JSON serialization issues and "$NaN" display.

**Source:** Health audit HIGH-5

**Files to Modify:**

- `backend/lambdas/jobs/list_jobs.py` -- Fix Decimal handling in response building

**Prerequisites:**

- Read `list_jobs.py` lines 106-112 to see the current conversion logic

**Implementation Steps:**

- Use `default=str` in the `success_response()` call (the function already supports
  `**json_kwargs`)
- OR: convert all Decimal values to float consistently before building the response
- The existing `success_response()` function accepts `default=str` via kwargs, so
  the simplest fix is: `return success_response(200, body, default=str)`

**Verification Checklist:**

- [x] All Decimal values in response are properly serialized
- [x] Test verifies Decimal cost values don't cause serialization errors

**Testing Instructions:**

- Write a test in `tests/unit/test_list_jobs.py` (create or extend):
  1. Mock DynamoDB to return items with Decimal cost values
  1. Verify the response body contains valid JSON with numeric cost values
- Run: `PYTHONPATH=. pytest tests/unit/test_list_jobs.py -v`

**Commit Message Template:**

```text
fix(lambda): fix Decimal serialization in list_jobs response

- Addresses health-audit HIGH-5
- Cost values now serialize consistently as strings via default=str
```

---

### Task 9: Fix template engine missing template handling

**Goal:** When a template is missing, the template engine returns HTML comments
that get sent to Bedrock as part of the prompt, causing garbage output. Raise an
exception instead.

**Source:** Eval stress CRITICAL-5, Health audit HIGH-7

**Files to Modify:**

- `backend/ecs_tasks/worker/template_engine.py` -- Raise exception on missing template

**Prerequisites:**

- Read `template_engine.py` lines 80-95 to understand the fallback behavior

**Implementation Steps:**

- Find where missing templates return HTML comment strings (e.g.,
  `<!-- template not found -->`)
- Replace with raising a `ValueError` or custom exception with a descriptive message
  including the template ID
- The caller (worker.py generation loop) should catch this and mark the job as FAILED
  with a clear error message

**Verification Checklist:**

- [x] Missing template raises an exception (not returns HTML comment)
- [x] Exception message includes the template identifier
- [x] Worker catches the exception and marks job FAILED
- [x] Test covers the missing template case

**Testing Instructions:**

- Write a test in `tests/unit/test_template_engine.py` (create or extend):
  1. Create a TemplateEngine with a non-existent template reference
  1. Verify rendering raises ValueError (or appropriate exception)
- Run: `PYTHONPATH=. pytest tests/unit/test_template_engine.py -v`

**Commit Message Template:**

```text
fix(worker): raise exception on missing template instead of HTML comment

- Addresses health-audit HIGH-7 and eval stress CRITICAL-5
- Missing templates now fail fast with clear error message
```

---

### Task 10: Add Jinja2 template render timeout

**Goal:** Malformed Jinja2 templates can cause infinite loops during render,
blocking the worker thread forever.

**Source:** Health audit HIGH-7, MEDIUM-17

**Files to Modify:**

- `backend/ecs_tasks/worker/template_engine.py` -- Add render timeout

**Implementation Steps:**

- Use Python's `signal.alarm()` to set a render timeout (e.g., 5 seconds)
- Wrap the Jinja2 render call in a try/finally that clears the alarm
- If the alarm fires, catch `signal.SIGALRM` and raise a `TimeoutError`
- Note: `signal.alarm` only works on the main thread. If the render runs in a
  thread, use `threading.Timer` instead to set a flag and check it
- Alternative: since the worker already uses `signal.SIGALRM` (line 99-109), reuse
  that mechanism or use `threading.Timer` to avoid conflict

**Verification Checklist:**

- [x] Template render has a timeout
- [x] Timeout raises an exception (not silent hang)
- [x] Does not conflict with existing SIGALRM usage in worker

**Testing Instructions:**

- Write a test that creates a template with a very long render time (e.g., deeply
  nested loops) and verify it times out within the configured limit
- Run: `PYTHONPATH=. pytest tests/unit/test_template_engine.py -v`

**Commit Message Template:**

```text
fix(worker): add timeout to Jinja2 template rendering

- Addresses health-audit HIGH-7, MEDIUM-17
- Prevents malformed templates from blocking worker indefinitely
```

## Phase Verification

- All backend tests pass: `PYTHONPATH=. pytest tests/ -v`
- All frontend tests pass: `cd frontend && npx vitest run`
- Linting passes: `npm run lint && npm run lint:backend`
- Each fix has at least one test covering the specific error condition
- No new warnings introduced
