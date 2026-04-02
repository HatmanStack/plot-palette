# Phase 1: [HYGIENIST] Cleanup and Simplification

## Phase Goal

Remove dead code, unused dependencies, and simplify overly complex patterns.
This is subtractive work -- the codebase should be smaller after this phase.

**Success criteria:** All identified dead code removed, unused Docker dependency
removed, dead validation removed, quick-win fixes applied.

**Estimated tokens:** ~12,000

## Prerequisites

- Phase 0 read and understood
- Repository cloned, dependencies installed
- Backend tests passing: `PYTHONPATH=. pytest tests/ -v` from repo root
- Frontend tests passing: `cd frontend && npx vitest run`

## Tasks

### Task 1: Remove unused curl dependency from Dockerfile

**Goal:** The Dockerfile installs `curl` but the health check uses `pgrep`, not `curl`.
Remove the unused dependency to reduce image size and attack surface.

**Source:** Health audit LOW-6

**Files to Modify:**

- `backend/ecs_tasks/worker/Dockerfile` -- Remove curl from apt-get install

**Implementation Steps:**

- Remove the `curl \` line from the `apt-get install` command
- If `curl` is the only package in the install command, remove the entire `RUN apt-get` block
- Verify the Dockerfile still builds (syntax check only -- no need to build the image)

**Verification Checklist:**

- [x] `curl` is no longer installed in the Dockerfile
- [x] Dockerfile syntax is valid (no trailing backslashes, no empty install commands)
- [x] Health check line still references `pgrep` (unchanged)

**Testing Instructions:**

- No automated tests needed -- this is a Dockerfile change
- Verify syntax: `docker build --check` or manual review

**Commit Message Template:**

```text
fix(docker): remove unused curl dependency from worker Dockerfile

- Addresses health-audit LOW-6
- Health check uses pgrep, not curl
```

---

### Task 2: Remove dead validation in models.py

**Goal:** The validator at `backend/shared/models.py:86-91` checks for
`COMPLETED && records_generated == 0` but this condition never triggers in normal
execution because the worker always creates records before marking COMPLETED.
Remove the dead validation code.

**Source:** Health audit HIGH-12 (dead validator)

**Files to Modify:**

- `backend/shared/models.py` -- Remove the dead validator method

**Prerequisites:**

- Read `backend/shared/models.py` to locate the exact validator
- Confirm no test depends on this validator

**Implementation Steps:**

- Find the Pydantic validator that checks `status == COMPLETED and records_generated == 0`
- Remove the entire validator method
- Search for any tests that reference this validator and remove them too
- Run existing model tests to verify nothing breaks

**Verification Checklist:**

- [x] Dead validator removed from `models.py`
- [x] No remaining references to this validator in tests
- [x] All existing model tests pass: `PYTHONPATH=. pytest tests/unit/test_shared.py -v`

**Testing Instructions:**

- Run existing tests to verify no regression
- No new tests needed (we are removing dead code)

**Commit Message Template:**

```text
fix(shared): remove dead COMPLETED/zero-records validator

- Addresses health-audit HIGH-12
- Validator never triggers during normal execution
```

---

### Task 3: Add default=str to error_response JSON serialization

**Goal:** The `error_response()` function uses `json.dumps()` without `default=str`,
which will fail if the error message contains a Decimal or datetime object. Add
`default=str` as a safety net.

**Source:** Health audit MEDIUM-16, Quick Win #2

**Files to Modify:**

- `backend/shared/lambda_responses.py` -- Add `default=str` to error_response

**Implementation Steps:**

- In the `error_response()` function, change `json.dumps({"error": message})` to
  `json.dumps({"error": message}, default=str)`
- Note: `success_response()` already accepts `**json_kwargs` so callers can pass
  `default=str` -- no change needed there

**Verification Checklist:**

- [x] `error_response()` uses `default=str` in `json.dumps()`
- [x] `success_response()` is unchanged
- [x] Existing tests pass

**Testing Instructions:**

- Write a test in `tests/unit/test_lambda_responses.py` (create if needed) that
  passes a Decimal value as part of the error message and verifies no exception
- Run: `PYTHONPATH=. pytest tests/unit/test_lambda_responses.py -v`

**Commit Message Template:**

```text
fix(shared): add default=str to error_response JSON serialization

- Addresses health-audit MEDIUM-16
- Prevents crash when error message contains Decimal or datetime
```

---

### Task 4: Fix S3 error code check in download handler

**Goal:** The download handler checks `e.response["Error"]["Code"] == "404"` but
S3 actually returns `"NoSuchKey"` (or `"404"` depending on the API call). For
`head_object`, the code is `"404"`. Verify the actual behavior and ensure the check
is correct.

**Source:** Health audit HIGH-3, Quick Win #3

**Files to Modify:**

- `backend/lambdas/jobs/download_job.py` -- Fix S3 error code comparison

**Prerequisites:**

- Read the file to understand the current check at line 88-92
- Note: S3 `head_object` returns error code `"404"` as a string (not `"NoSuchKey"`)
  for missing objects. This is actually correct behavior for HeadObject. However,
  best practice is to check for both.

**Implementation Steps:**

- Change the error code check to handle both `"404"` and `"NoSuchKey"`:
  `if e.response["Error"]["Code"] in ("404", "NoSuchKey"):`
- This makes the handler robust regardless of which S3 API behavior applies

**Verification Checklist:**

- [x] Error code check handles both `"404"` and `"NoSuchKey"`
- [x] Test covers the error path

**Testing Instructions:**

- Write a test in `tests/unit/test_download_job.py` (create if needed) that mocks
  a `ClientError` with code `"404"` and verifies a 404 response is returned
- Write a second test with code `"NoSuchKey"` and verify same behavior
- Run: `PYTHONPATH=. pytest tests/unit/test_download_job.py -v`

**Commit Message Template:**

```text
fix(lambda): handle both S3 error codes in download handler

- Addresses health-audit HIGH-3
- head_object can return "404" or "NoSuchKey" depending on context
```

---

### Task 5: Remove unused lru_cache on DynamoDB resource factory

**Goal:** `get_dynamodb_resource()` uses `lru_cache(maxsize=1)` but in Lambda,
each invocation is a fresh process import so the cache provides no benefit for
the resource factory. However, within a single Lambda container lifetime (warm
starts), the cache IS useful. Verify whether other `get_*` functions use the same
pattern and document the intent.

**Source:** Health audit LOW-8

**Files to Modify:**

- None -- after investigation, this is intentional. `lru_cache` on Lambda client
  factories IS useful for warm-start container reuse. The health audit finding is
  incorrect.

**Implementation Steps:**

- Read `backend/shared/aws_clients.py` and verify that `lru_cache` is used on
  multiple client factories
- Add a brief comment above the `lru_cache` decorator explaining why it exists:
  "Cache for Lambda warm starts -- same container may handle multiple invocations"
- This is a documentation-only change

**Verification Checklist:**

- [ ] Comment added explaining the cache purpose
- [ ] No functional changes to aws_clients.py

**Testing Instructions:**

- No new tests needed

**Commit Message Template:**

```text
docs(shared): clarify lru_cache intent on AWS client factories

- Addresses health-audit LOW-8
- Cache is useful for Lambda warm starts, not per-invocation
```

## Phase Verification

- All backend tests pass: `PYTHONPATH=. pytest tests/ -v`
- All frontend tests pass: `cd frontend && npx vitest run`
- Linting passes: `npm run lint && npm run lint:backend`
- Dockerfile syntax is valid
- No dead code remains from identified findings
