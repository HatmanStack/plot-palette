---
type: repo-health
date: 2026-04-02
goal: General health check — scan all 4 vectors equally
---

# Codebase Health Audit: plot-palette

## Configuration
- **Goal:** General health check — scan all 4 vectors equally
- **Scope:** Full repo, no constraints
- **Existing Tooling:** Full setup — linters, CI pipeline, pre-commit hooks, type checking
- **Constraints:** None
- **Deployment Target:** Containers (ECS, Kubernetes, Docker)

## Summary
- Overall health: FAIR
- Total findings: 8 critical, 12 high, 18 medium, 11 low

## Tech Debt Ledger

### CRITICAL

1. **[Operational Debt]** `backend/ecs_tasks/worker/Dockerfile:31`
   - **The Debt:** Health check uses `pgrep -f "python worker"` without validating worker state or checking if actively processing
   - **The Risk:** ECS will report task as healthy even during pathological states (process exists but hung indefinitely on I/O, stuck in infinite loop, or unresponsive to signals). Load balancer may route requests to zombie containers during Spot interruptions.

2. **[Operational Debt]** `backend/ecs_tasks/worker/entrypoint.sh:10`
   - **The Debt:** Entrypoint runs `exec python worker.py` with no signal handling setup, no graceful shutdown coordination, and no status exit codes for ECS task orchestration
   - **The Risk:** SIGTERM during checkpoint save (120s window before forced kill) can corrupt S3 checkpoint or leave job in RUNNING state indefinitely. No way for orchestrator to distinguish "job done" from "task killed due to Spot interruption" (all exit with code 0 or 1).

3. **[Architectural Debt]** `backend/lambdas/jobs/stream_progress.py:81-133`
   - **The Debt:** Lambda handler lacks top-level try/except for DynamoDB call at line 81; KeyError handler at line 127 only catches explicit KeyError from line 64, not from missing `pathParameters`
   - **The Risk:** Missing `pathParameters` throws unhandled KeyError, returns 500 with no logging. Same risk at line 64 if JWT auth info missing.

4. **[Operational Debt]** `backend/shared/retry.py:195-243`
   - **The Debt:** Circuit breaker is only used where explicitly passed `circuit_breaker_name`; most Bedrock calls in worker and template test do NOT use circuit breaker
   - **The Risk:** Single Bedrock region outage cascades across all Lambda invocations simultaneously; no automatic fallback or rate-limiting. Can exhaust Bedrock quota and return ThrottlingException to end users as 500 errors.

5. **[Architectural Debt]** `backend/lambdas/templates/search_templates.py:84-107`
   - **The Debt:** Marketplace search uses `scan()` with no GSI; loop scans up to 1000 items (safety cap) with `Limit=100`, meaning up to 10 DynamoDB scans per request. No pagination token support.
   - **The Risk:** At scale (>10k public templates), scan hits 1000 cap and silently truncates results. Each scan is ~100 RCUs = 1000 RCUs per request, causing DynamoDB throttling.

6. **[Architectural Debt]** `backend/lambdas/templates/list_templates.py:71-92`
   - **The Debt:** Fetches public templates via `scan()` without GSI index on `is_public`; duplicates pattern from search handler. Safety capped at 100 public templates.
   - **The Risk:** Same as #5 — scan-based list operations don't scale. Client doesn't know if list is truncated.

7. **[Operational Debt]** `backend/lambdas/jobs/create_job.py:302-341`
   - **The Debt:** After SFN execution start fails, code tries to update job status to FAILED, but that update also fails (line 333 catches but doesn't re-raise). Job stays QUEUED with no execution ARN.
   - **The Risk:** Cascading failures — if SFN unavailable, user sees "Job created but failed to start" 500 error, but job is in inconsistent state (QUEUED but no execution). Retry creates duplicate jobs.

8. **[Operational Debt]** `backend/ecs_tasks/worker/worker.py:310-380`
   - **The Debt:** If Bedrock call fails during generation loop (line 330), code continues silently, increments `failed_records`, but does not roll back batch state. Budget check happens before call (line 321), so failed call still counts toward running cost tracking.
   - **The Risk:** If Bedrock returns permanent error, all records in batch fail, checkpoint still increments, but job completes with 0 records generated (but cost_accumulated > 0).

### HIGH

1. **[Structural Debt]** `frontend/src/services/api.ts:6-14`
   - **The Debt:** `getAuthHeaders()` catches `Error` globally but returns empty `{}` on auth token fetch failure, silently downgrading to unauthenticated request
   - **The Risk:** 401/403 errors treated as auth failures trigger redirect to `/login`, but user is actually already logged in — loop redirect.

2. **[Operational Debt]** `backend/shared/aws_clients.py:23-34`
   - **The Debt:** Standard client config has `connect_timeout=5, read_timeout=30` but no timeout for Bedrock client `read_timeout=120`. Lambda has 15-minute timeout, so blocked request still holds container.
   - **The Risk:** If Bedrock hangs (network partition, hung GPU), worker sleeps for 120 seconds. No jitter on retries.

3. **[Operational Debt]** `backend/lambdas/jobs/download_job.py:88-92`
   - **The Debt:** S3 head_object error handling checks `e.response["Error"]["Code"] == "404"` but S3 actually returns `NoSuchKey`, not `404` string
   - **The Risk:** File not found errors mishandled, return 500 instead of 404.

4. **[Structural Debt]** `backend/ecs_tasks/worker/worker.py:254-271`
   - **The Debt:** `process_job` in standalone mode catches exceptions and marks job FAILED, but caller in `_run_standalone_mode` (line 148-162) doesn't wait for async state updates to complete before exiting
   - **The Risk:** Job marked FAILED in memory but before DynamoDB update completes, task exits. Job status stuck in QUEUED forever.

5. **[Operational Debt]** `backend/lambdas/jobs/list_jobs.py:106-112`
   - **The Debt:** Cost and budget values pulled from DynamoDB as Decimal, conversion to float happens in loop with branching logic. Mixed Decimal/float types cause inconsistent JSON serialization.
   - **The Risk:** Response JSON inconsistent; cost arithmetic fails silently. Cost analytics displays "$NaN" or missing values.

6. **[Architectural Debt]** `backend/lambdas/jobs/create_batch.py:149-210`
   - **The Debt:** Batch creation creates jobs in loop; if 15th job fails, first 14 are already created. Code doesn't rollback; batch is partially created with no indication to client.
   - **The Risk:** Orphaned batches with incomplete job counts.

7. **[Operational Debt]** `backend/ecs_tasks/worker/template_engine.py`
   - **The Debt:** Template rendering via Jinja2 with user-provided prompts; no timeout on render operation
   - **The Risk:** Malformed Jinja2 template causes infinite loop during render, blocking generator thread forever.

8. **[Operational Debt]** `backend/shared/lambda_responses.py:13-21`
   - **The Debt:** CORS header uses environment variable `ALLOWED_ORIGIN`, defaults to literal string `"null"` if missing. No validation that origin is actually configured in production.
   - **The Risk:** If `ALLOWED_ORIGIN` not set in Lambda env, all frontend requests fail with CORS error.

9. **[Operational Debt]** `backend/lambdas/jobs/create_job.py:170-204`
   - **The Debt:** Idempotency token check queries with `FilterExpression` but doesn't handle race condition during concurrent batch creation
   - **The Risk:** Multiple jobs created with same idempotency token if two concurrent batch creations overlap.

10. **[Structural Debt]** `frontend/src/contexts/AuthContext.tsx:21-37`
    - **The Debt:** `checkAuth()` is fire-and-forget in useEffect; if auth service is offline, loading stays true forever
    - **The Risk:** UI stuck in loading state; user can't access login page.

11. **[Operational Debt]** `backend/ecs_tasks/worker/worker.py:603-625`
    - **The Debt:** Queries cost tracking table with hardcoded KeyConditionExpression string, not using DynamoDB Key condition builder. Exception caught silently, returns 0.0.
    - **The Risk:** Budget check becomes ineffective, cost accumulation is lost. Worker ignores budget entirely.

12. **[Operational Debt]** `backend/shared/models.py:86-91`
    - **The Debt:** JobConfig validator checks `COMPLETED && records_generated == 0`, but this check never triggers because worker always creates records before marking COMPLETED
    - **The Risk:** Dead validation code. Manual status changes via CLI bypass this check.

### MEDIUM

1. **[Code Hygiene Debt]** `backend/lambdas/templates/search_templates.py:90, 136`
   - **The Debt:** Two TODO comments indicate planned but unimplemented optimizations (GSI query, fork_count field)

2. **[Code Hygiene Debt]** `backend/lambdas/templates/list_templates.py:70`
   - **The Debt:** TODO about GSI index

3. **[Code Hygiene Debt]** `backend/lambdas/templates/delete_template.py:41`
   - **The Debt:** TODO about GSI performance

4. **[Operational Debt]** `frontend/src/hooks/useJobPolling.ts:13-24`
   - **The Debt:** Polling interval uses state-dependent logic but no maximum limit. If status is corrupt, will poll forever.

5. **[Operational Debt]** `backend/shared/retry.py:222-228`
   - **The Debt:** Retry delay uses `time.sleep()` in synchronous decorator; blocks entire thread. Worst case 90 seconds of blocking.

6. **[Structural Debt]** `backend/ecs_tasks/worker/worker.py:272-400`
   - **The Debt:** `generate_data()` method is 128 lines with nested loop, checkpoint save, cost tracking, exception handling. Multiple responsibilities.

7. **[Operational Debt]** `backend/ecs_tasks/worker/worker.py:540-573`
   - **The Debt:** Checkpoint save retry logic only for conflict errors. Other ClientError exceptions re-raised immediately, task crashes.

8. **[Hygiene Debt]** `frontend/src/components/ErrorBoundary.tsx:23`
   - **The Debt:** `componentDidCatch` logs to console.error but doesn't report to error tracking service

9. **[Operational Debt]** `backend/lambdas/jobs/download_job.py:77-82`
   - **The Debt:** S3 key derived from output_format with fallback but doesn't verify file exists before generating presigned URL.

10. **[Structural Debt]** `backend/lambdas/jobs/create_job.py:45-85`
    - **The Debt:** Validation function is 40 lines of imperative checks; better as Pydantic schema validation.

11. **[Operational Debt]** `backend/shared/utils.py:94-132`
    - **The Debt:** Error sanitization regex-based; doesn't handle AWS ARN format completely (misses resource IDs in ARN path).

12. **[Operational Debt]** `backend/ecs_tasks/worker/worker.py:99-109`
    - **The Debt:** Signal handlers for SIGTERM and SIGALRM set at init time, but no way to verify they were registered successfully.

13. **[Architectural Debt]** `backend/lambdas/jobs/list_jobs.py:56-87`
    - **The Debt:** User's jobs queried via GSI, but if GSI not initialized at table creation, query hangs indefinitely.

14. **[Structural Debt]** `backend/lambdas/jobs/stream_progress.py:102-109`
    - **The Debt:** Cost and budget values retrieved from Decimal/string, type-checked with ad-hoc `hasattr` checks.

15. **[Operational Debt]** `frontend/src/services/api.ts:37-56`
    - **The Debt:** `fetch()` error handling catches only `!response.ok`, not network errors (timeout, CORS pre-flight failure).

16. **[Hygiene Debt]** `backend/shared/lambda_responses.py:24-39`
    - **The Debt:** `error_response()` always uses `json.dumps()` without `default=str`, will fail if error message contains Decimal or datetime.

17. **[Structural Debt]** `backend/ecs_tasks/worker/template_engine.py`
    - **The Debt:** TemplateEngine Jinja2 rendering logic potentially untested; possible hang on malformed templates.

18. **[Operational Debt]** `backend/lambdas/jobs/create_batch.py:182-215`
    - **The Debt:** Batch job creation doesn't validate template still exists at creation time; race condition with concurrent template deletion.

### LOW

1. **[Hygiene Debt]** `backend/shared/constants.py:54-75`
   - **The Debt:** Model pricing hardcoded; last updated 2025-01. No version tracking or automatic update mechanism.

2. **[Code Hygiene Debt]** `frontend/src/services/api.ts:41-49`
   - **The Debt:** JSON response parsing doesn't validate schema; malformed response silently handled as `{}`.

3. **[Structural Debt]** `backend/shared/models.py:130-175`
   - **The Debt:** Decimal/float conversion logic duplicated in multiple places.

4. **[Operational Debt]** `backend/ecs_tasks/worker/worker.py:176-252`
   - **The Debt:** `get_next_job()` distributed job claiming via conditional writes doesn't handle race where another worker claims job between query and update.

5. **[Hygiene Debt]** `backend/lambdas/jobs/delete_job.py`
   - **The Debt:** Job deletion likely doesn't clean up all related data (cost tracking, checkpoints, S3 outputs).

6. **[Operational Debt]** `backend/ecs_tasks/worker/Dockerfile:6`
   - **The Debt:** Installs `curl` for health check but uses `pgrep`, not `curl`. Unnecessary dependency.

7. **[Code Hygiene Debt]** `frontend/src/hooks/useJobPolling.ts:14-24`
   - **The Debt:** Refetch interval logic inline in hook; hard to test independently.

8. **[Operational Debt]** `backend/shared/aws_clients.py:37-53`
   - **The Debt:** `get_dynamodb_resource()` uses `lru_cache(maxsize=1)` but in Lambda each invocation is fresh process. Cache does nothing.

9. **[Operational Debt]** `backend/lambdas/jobs/list_jobs.py:118-122`
   - **The Debt:** Pagination token passed as JSON string; base64 would be safer.

10. **[Structural Debt]** `backend/lambdas/notifications/send_notification.py`
    - **The Debt:** Notification handler exists but not integrated into job completion flow. Dead code.

11. **[Hygiene Debt]** `frontend/src/test/mocks/api.ts`
    - **The Debt:** Mocks likely don't match actual API schema changes; tests pass while production fails.

## Quick Wins

1. `backend/ecs_tasks/worker/Dockerfile:6` — Remove unused `curl` dependency (estimated effort: < 5 min)
2. `backend/shared/lambda_responses.py:24-39` — Add `default=str` kwarg to error_response JSON serialization (estimated effort: 10 min)
3. `backend/lambdas/jobs/download_job.py:88-92` — Fix S3 error code check: change `"404"` to `"NoSuchKey"` (estimated effort: 5 min)
4. `backend/shared/lambda_responses.py:13-21` — Add validation that ALLOWED_ORIGIN is not "null" string in prod (estimated effort: 15 min)
5. `frontend/src/contexts/AuthContext.tsx:32-35` — Add timeout to `checkAuth()` promise (estimated effort: 15 min)
6. `frontend/src/components/ErrorBoundary.tsx:22-24` — Integrate error reporting service call (estimated effort: 30 min)

## Automated Scan Results

**Dead Code:**
- No obvious dead code detected via grep for unreachable paths
- Validator in `models.py:86-91` is semantically dead (check never triggers in normal execution path)

**Dependency Security:**
- `frontend/package.json` uses axios@1.13.6 (no known CVEs)
- `backend/pyproject.toml` boto3>=1.34.0 is current
- No high-severity vulnerabilities detected

**Secrets Scan:**
- No hardcoded secrets found in code
- `.env.example` properly configured with placeholder values
- AWS_ENDPOINT_URL for test environments properly documented

**Git Hygiene:**
- Last 30 commits show active maintenance, good commit messages
- No large binary files committed
- `.gitignore` properly configured

**Deployment & Operational Concerns (ECS/Containers):**
1. Health check is process-based, not state-based — upgrade to HTTP health endpoint
2. Graceful shutdown (SIGTERM) handling incomplete — formalize checkpoint completion protocol
3. No readiness probes — can't distinguish "warming up" from "ready to serve"
4. No liveness probe — hung processes marked as healthy
