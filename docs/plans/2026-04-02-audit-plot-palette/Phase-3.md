# Phase 3: [IMPLEMENTER] Performance and Architecture Improvements

## Phase Goal

Address performance bottlenecks (DynamoDB scan-based queries) and architectural
issues (entrypoint signal handling, health check improvements, circuit breaker
gaps). These changes improve scalability and operational reliability.

**Success criteria:** DynamoDB scans replaced with GSI queries for public template
operations, worker entrypoint handles signals properly, health check validates
worker state.

**Estimated tokens:** ~15,000

## Prerequisites

- Phase 2 complete (error handling fixes in place)
- All tests passing

## Tasks

### Task 1: Add GSI for public template queries (infrastructure change)

**Goal:** Replace DynamoDB scan-based queries for public templates with a GSI.
Currently `search_templates` and `list_templates` scan the entire table filtering
by `is_public`, which does not scale.

**Source:** Health audit CRITICAL-5, CRITICAL-6, MEDIUM-1/2/3; Eval performance/pragmatism

**Files to Modify:**

- `backend/template.yaml` -- Add GSI definition to Templates table
- `backend/lambdas/templates/search_templates.py` -- Use GSI query instead of scan
- `backend/lambdas/templates/list_templates.py` -- Use GSI query instead of scan
- `backend/lambdas/templates/delete_template.py` -- Use GSI if applicable

**Implementation Steps:**

- Add a GSI named `is_public-created_at-index` (or similar) to the Templates table
  in `backend/template.yaml`:
  - Partition key: `is_public` (String -- "true"/"false")
  - Sort key: `created_at` (String -- ISO 8601)
- In `search_templates.py`, replace the `scan()` loop with a `query()` on the GSI:
  - Use `KeyConditionExpression` for `is_public = "true"`
  - Apply text search as a `FilterExpression` on the query (still server-side filter
    but over a smaller dataset)
  - Support pagination via `ExclusiveStartKey`/`LastEvaluatedKey`
- In `list_templates.py`, replace the `scan()` with a `query()` on the same GSI
- In `delete_template.py`, check if there is a scan that can benefit from the GSI
- Remove the TODO comments about GSI (MEDIUM-1/2/3) since the work is now done

**Verification Checklist:**

- [x] GSI defined in template.yaml
- [x] search_templates uses `query()` on the GSI
- [x] list_templates uses `query()` on the GSI
- [x] TODO comments about GSI removed
- [x] Pagination support (ExclusiveStartKey) present in both handlers
- [x] Tests verify query behavior with moto-created GSI

**Testing Instructions:**

- Write integration tests in `tests/integration/test_templates_api.py` (or extend):
  1. Create a DynamoDB table with the GSI using moto
  1. Insert public and private templates
  1. Query via the GSI and verify only public templates returned
  1. Test pagination with `ExclusiveStartKey`
- Run: `PYTHONPATH=. pytest tests/integration/test_templates_api.py -v`

**Commit Message Template:**

```text
perf(lambda): replace DynamoDB scans with GSI for public template queries

- Addresses health-audit CRITICAL-5, CRITICAL-6, MEDIUM-1/2/3
- Adds is_public-created_at-index GSI to Templates table
- Removes TODO comments about GSI optimization
```

---

### Task 2: Improve worker entrypoint signal handling

**Goal:** The entrypoint script runs `exec python worker.py` with no signal setup.
Add basic signal trapping so SIGTERM is properly relayed and the exit code
distinguishes "job done" from "task killed."

**Source:** Health audit CRITICAL-2

**Files to Modify:**

- `backend/ecs_tasks/worker/entrypoint.sh` -- Add signal trapping

**Implementation Steps:**

- Add a SIGTERM trap that forwards the signal to the Python process:

```bash
# Trap SIGTERM and forward to child process
trap 'kill -TERM $PID' TERM

python worker.py &
PID=$!
wait $PID
EXIT_CODE=$?

# Exit with the child's exit code
exit $EXIT_CODE
```

- This allows the Python worker (which already handles SIGTERM in its __init__)
  to receive the signal and perform graceful shutdown
- Different exit codes let ECS/Step Functions distinguish outcomes:
  - 0 = job completed successfully
  - 1 = job failed (unrecoverable)
  - 143 = killed by SIGTERM (Spot interruption)

**Verification Checklist:**

- [x] Entrypoint traps SIGTERM
- [x] SIGTERM is forwarded to the Python process
- [x] Exit code from Python process is preserved
- [x] No longer uses `exec` (which prevents signal trapping)

**Testing Instructions:**

- Manual verification: review the script logic
- The signal handling in the Python worker is already tested
- No automated test needed for bash scripts in this context

**Commit Message Template:**

```text
fix(worker): add SIGTERM forwarding in entrypoint.sh

- Addresses health-audit CRITICAL-2
- ECS can now distinguish job completion from Spot interruption via exit code
```

---

### Task 3: Improve Docker health check

**Goal:** The health check uses `pgrep -f "python worker"` which only checks if
the process exists, not if it is healthy. Add a state-based check.

**Source:** Health audit CRITICAL-1

**Files to Modify:**

- `backend/ecs_tasks/worker/Dockerfile` -- Update HEALTHCHECK
- `backend/ecs_tasks/worker/worker.py` -- Add health file mechanism

**Implementation Steps:**

- In the worker, write a health marker file (e.g., `/tmp/worker_healthy`) on each
  successful checkpoint or heartbeat cycle
- Update the Dockerfile HEALTHCHECK to check both process existence AND recency of
  the health file:

```text
HEALTHCHECK --interval=30s --timeout=5s CMD \
  pgrep -f "python worker" && \
  find /tmp/worker_healthy -mmin -2 | grep -q . || exit 1
```

- The health file is touched periodically (e.g., every checkpoint save or every N
  records processed)
- If the worker hangs, the file becomes stale and the health check fails

**Verification Checklist:**

- [x] Worker writes a health marker file periodically
- [x] HEALTHCHECK validates file recency, not just process existence
- [x] Health file is written in the main processing loop
- [x] Test verifies health file is created/updated

**Testing Instructions:**

- Write a test in `tests/unit/test_worker.py`:
  1. Mock the file system (or use tmp_path fixture)
  1. Verify the worker touches the health file during processing
- Run: `PYTHONPATH=. pytest tests/unit/test_worker.py -v`

**Commit Message Template:**

```text
fix(worker): add state-based health check with marker file

- Addresses health-audit CRITICAL-1
- Health check now detects hung workers via stale marker file
```

---

### Task 4: Move budget check outside hot loop in worker

**Goal:** The worker performs an O(n) budget check per record in the generation
loop. Pre-compute cost-per-record and check budget less frequently.

**Source:** Eval performance, Health audit MEDIUM-6 (related)

**Files to Modify:**

- `backend/ecs_tasks/worker/worker.py` -- Optimize budget checking

**Prerequisites:**

- Read `worker.py` lines 320-323 to understand the current budget check

**Implementation Steps:**

- Calculate the estimated cost-per-record before the loop starts (from model pricing
  and estimated tokens)
- Check budget every N records (e.g., every 10 or every batch) instead of every record
- Keep the total cost accumulation accurate (it still tracks actual costs)
- The key optimization: replace per-record DynamoDB query for budget with arithmetic
  check against pre-computed estimate

**Verification Checklist:**

- [x] Budget check frequency reduced (not every record)
- [x] Cost tracking accuracy preserved
- [x] Budget exceeded condition still triggers job stop
- [x] Test verifies budget check triggers at correct intervals

**Testing Instructions:**

- Write a test in `tests/unit/test_worker.py`:
  1. Set a low budget limit
  1. Generate records and verify budget check triggers before exceeding the limit
  1. Verify check happens every N records, not every record
- Run: `PYTHONPATH=. pytest tests/unit/test_worker.py -v`

**Commit Message Template:**

```text
perf(worker): reduce budget check frequency in generation loop

- Addresses eval performance target
- Budget check now runs every N records instead of per-record
```

---

### Task 5: Add useJobPolling maximum poll limit

**Goal:** The polling hook has no maximum iteration limit. If the job status is
corrupt, it will poll forever. Add a maximum poll count.

**Source:** Health audit MEDIUM-4

**Files to Modify:**

- `frontend/src/hooks/useJobPolling.ts` -- Add max poll count

**Implementation Steps:**

- Add a counter that tracks how many poll cycles have occurred
- After a maximum number of polls (e.g., 300 at 2-second intervals = 10 minutes),
  stop polling and set an error state
- Expose the error state so the UI can show a "polling timed out" message
- Reset the counter when the job ID changes or status transitions

**Verification Checklist:**

- [x] Polling stops after max iterations
- [x] Error state is exposed for UI consumption
- [x] Counter resets on job change
- [x] Test verifies polling stops at max

**Testing Instructions:**

- Write a test in `frontend/src/test/hooks/useJobPolling.test.tsx` (or extend):
  1. Mock the API to always return a non-terminal status
  1. Use fake timers to advance through max poll cycles
  1. Verify polling stops and error state is set
- Run: `cd frontend && npx vitest run src/test/hooks/useJobPolling.test.tsx`

**Commit Message Template:**

```text
fix(frontend): add maximum poll limit to useJobPolling

- Addresses health-audit MEDIUM-4
- Prevents infinite polling on corrupt job status
```

---

### Task 6: Add structured logging to useJobStream parse errors

**Goal:** `useJobStream.ts` silently ignores parse errors. Add structured logging
so failures are visible during development and can be tracked in production.

**Source:** Eval code quality

**Files to Modify:**

- `frontend/src/hooks/useJobStream.ts` -- Add error logging on parse failures

**Prerequisites:**

- Read `useJobStream.ts` lines 68-70 to see the silent catch

**Implementation Steps:**

- In the catch block that silently ignores parse errors, add `console.error()` with
  the raw data that failed to parse and the error message
- This is intentional error absorption (the stream continues), so add a comment
  explaining why: "Parse errors are non-fatal -- stream may contain partial data"
- Consider incrementing an error counter that triggers fallback to polling sooner

**Verification Checklist:**

- [ ] Parse errors are logged to console.error
- [ ] Comment explains why errors are absorbed
- [ ] Stream continues after parse error (existing behavior preserved)

**Testing Instructions:**

- Write a test in `frontend/src/test/hooks/useJobStream.test.ts` (or extend):
  1. Mock EventSource to send invalid JSON
  1. Verify console.error is called with the parse error
  1. Verify the hook does not crash
- Run: `cd frontend && npx vitest run src/test/hooks/useJobStream.test.ts`

**Commit Message Template:**

```text
fix(frontend): add structured logging to useJobStream parse errors

- Addresses eval code quality target
- Parse errors now logged instead of silently swallowed
```

## Phase Verification

- All backend tests pass: `PYTHONPATH=. pytest tests/ -v`
- All frontend tests pass: `cd frontend && npx vitest run`
- Linting passes: `npm run lint && npm run lint:backend`
- CloudFormation lint passes: `cfn-lint backend/template.yaml`
- Template search/list no longer use DynamoDB scan
- Worker health check validates state, not just process existence
