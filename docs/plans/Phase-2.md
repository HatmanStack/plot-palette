# Phase 2: Backend Tests

## Phase Goal

Expand backend unit test coverage for Lambda handlers and Worker/ECS failure scenarios. Focus on error paths, edge cases, and failure recovery that aren't covered by existing tests. Tests must run without AWS connectivity using moto and manual mocking.

**Success Criteria:**
- Lambda handlers have tests for input validation, auth failures, and AWS service errors
- Worker has tests for Spot interruption, Bedrock failures, and S3/DynamoDB errors
- All tests pass with `npm run test:backend`
- No AWS credentials required

**Estimated Tokens:** ~40,000

## Prerequisites

- Phase 0 complete (all 3 tasks)
- Phase 1 complete (all 10 tasks)
- Verify Phase 0 outputs exist before starting:
  - `tests/conftest.py` - shared AWS mocks
  - `tests/fixtures/lambda_events.py` - event factories
  - `tests/fixtures/dynamodb_items.py` - item factories
- Verify `backend/requirements-dev.txt` contains: `pytest`, `pytest-asyncio`, `pytest-cov`, `moto[all]`

---

## Tasks

### Task 1: Test Lambda Input Validation Errors

**Goal:** Test that Lambda handlers properly reject malformed and invalid input.

**Files to Create:**
- `tests/unit/test_lambda_validation.py`

**Prerequisites:**
- Phase 0 Task 2 complete (Lambda event factory)

**Implementation Steps:**

1. **Set up test module structure**
   - Import Lambda handlers with explicit paths:
     ```python
     from backend.lambdas.jobs.create_job import lambda_handler as create_job_handler
     from backend.lambdas.jobs.get_job import lambda_handler as get_job_handler
     from backend.lambdas.jobs.delete_job import lambda_handler as delete_job_handler
     from backend.lambdas.templates.create_template import lambda_handler as create_template_handler
     from backend.lambdas.seed_data.validate_seed_data import lambda_handler as validate_seed_data_handler
     ```
   - Import event factory from fixtures
   - Create test class `TestCreateJobValidation`

2. **Test missing required fields**
   - Create event with empty body
   - Call `create_job.lambda_handler(event, context)`
   - Verify 400 status code
   - Verify error message mentions missing field

3. **Test invalid JSON body**
   - Create event with body `"not valid json"`
   - Verify 400 status code
   - Verify error message indicates JSON parse error

4. **Test invalid budget_limit values**
   - Test with negative value: `{"budget_limit": -10}`
   - Test with zero: `{"budget_limit": 0}`
   - Test with too high: `{"budget_limit": 2000}` (max is 1000)
   - Test with non-numeric: `{"budget_limit": "fifty"}`
   - Verify 400 for each with appropriate message

5. **Test invalid output_format**
   - Test with invalid format: `{"output_format": "XML"}`
   - Verify 400 with message listing valid formats

6. **Test invalid num_records values**
   - Test with zero: `{"num_records": 0}`
   - Test with negative: `{"num_records": -5}`
   - Test with too high: `{"num_records": 2000000}` (max 1M)
   - Test with non-integer: `{"num_records": 100.5}`
   - Verify 400 for each

7. **Test missing template_id**
   - Provide all fields except template_id
   - Verify 400 with missing field message

8. **Test missing seed_data_path**
   - Provide all fields except seed_data_path
   - Verify 400 with missing field message

9. **Repeat pattern for other Lambda handlers**
   - `get_job`: test invalid job_id format
   - `delete_job`: test invalid job_id format
   - `create_template`: test missing required fields
   - `validate_seed_data`: test invalid JSON structure

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_lambda_validation.py`
- [x] All create_job validation cases tested
- [x] Other Lambda validation cases tested
- [x] All tests return appropriate 400 status codes
- [x] Tests pass: `pytest tests/unit/test_lambda_validation.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_lambda_validation.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Lambda input validation tests

- Test create_job validation for all fields
- Test validation in other Lambda handlers
- Verify appropriate error responses
```

---

### Task 2: Test Lambda Authorization Failures

**Goal:** Test that Lambda handlers properly handle authorization failures.

**Files to Create:**
- `tests/unit/test_lambda_auth.py`

**Prerequisites:**
- Phase 0 Task 2 complete

**Implementation Steps:**

1. **Test missing JWT claims**
   - Create event without `requestContext.authorizer.jwt.claims`
   - Verify 400 or 401 status code
   - Verify appropriate error message

2. **Test missing user_id (sub) claim**
   - Create event with JWT but no `sub` claim
   - Verify error response

3. **Test resource access by wrong user**
   - Create job owned by user-A
   - Try to access/delete with user-B credentials
   - Mock DynamoDB to return job with different user_id
   - Verify 403 or 404 status (depending on implementation)

4. **Test template access by wrong user**
   - Create template owned by user-A
   - Try to access/update/delete with user-B credentials
   - Verify appropriate error

5. **Test job operations on non-existent jobs**
   - Try to get job that doesn't exist
   - Mock DynamoDB to return empty Item
   - Verify 404 status

6. **Test delete on already-deleted resource**
   - Mock DynamoDB conditional check failure
   - Verify appropriate error handling

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_lambda_auth.py`
- [x] Missing auth context tested
- [x] Wrong user access tested
- [x] Non-existent resource tested
- [x] Tests pass: `pytest tests/unit/test_lambda_auth.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_lambda_auth.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Lambda authorization tests

- Test missing and invalid JWT claims
- Test cross-user access attempts
- Test non-existent resource handling
```

---

### Task 3: Test Lambda AWS Service Errors

**Goal:** Test Lambda handler behavior when AWS services fail.

**Files to Create:**
- `tests/unit/test_lambda_aws_errors.py`

**Prerequisites:**
- Phase 0 Task 2 complete
- moto configured for DynamoDB and S3 mocking

**Implementation Steps:**

1. **Test DynamoDB read failures**
   - Mock `get_item` to raise `ClientError` with `InternalError`
   - Call get_job handler
   - Verify 500 status with generic error message
   - Verify error is logged (mock logger if needed)

2. **Test DynamoDB write failures**
   - Mock `put_item` to raise `ClientError`
   - Call create_job handler with valid input
   - Verify 500 status
   - Verify partial writes are handled (rollback attempted)

3. **Test DynamoDB conditional check failures**
   - Mock `update_item` to raise `ConditionalCheckFailedException`
   - Verify appropriate handling (retry or error)

4. **Test S3 presigned URL generation failure**
   - Mock S3 client to raise `ClientError`
   - Call generate_upload_url handler
   - Verify 500 status

5. **Test ECS task start failure**
   - Mock `ecs_client.run_task` to raise `ClientError`
   - Call create_job (which starts worker task)
   - Verify job is created but error is logged
   - Verify job status reflects issue (or is handled gracefully)

6. **Test DynamoDB throttling**
   - Mock `ProvisionedThroughputExceededException`
   - Verify handler behavior (retry or error)

7. **Test S3 read failures in seed_data validation**
   - Mock S3 `get_object` to raise `NoSuchKey`
   - Verify appropriate error message

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_lambda_aws_errors.py`
- [x] DynamoDB read/write failures tested
- [x] S3 failures tested
- [x] ECS failures tested
- [x] All return 500 with safe error messages (no internal details leaked)
- [x] Tests pass: `pytest tests/unit/test_lambda_aws_errors.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_lambda_aws_errors.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Lambda AWS error handling tests

- Test DynamoDB read/write/throttling failures
- Test S3 operation failures
- Test ECS task start failures
- Verify safe error responses
```

---

### Task 4: Test Worker Spot Interruption Handling

**Goal:** Test the Worker's graceful shutdown and checkpoint saving on SIGTERM.

**Files to Create:**
- `tests/unit/test_worker_spot_interruption.py`

**Prerequisites:**
- Phase 0 Task 2 complete
- Understanding of Worker signal handling

**Implementation Steps:**

1. **Set up Worker test environment**
   - Mock all AWS clients (DynamoDB, S3, Bedrock)
   - Mock environment variables
   - Create Worker instance without running main loop

2. **Test SIGTERM handler sets shutdown flag**
   - Access `worker.shutdown_requested`
   - Call `worker.handle_shutdown(signal.SIGTERM, None)`
   - Verify `worker.shutdown_requested` is True

3. **Test generation loop checks shutdown flag**
   - Start generation with 100 records
   - Set `shutdown_requested = True` after 10 records
   - Verify loop exits early
   - Verify checkpoint is saved with current progress

4. **Test checkpoint contains correct data on interruption**
   - Trigger shutdown during generation
   - Capture checkpoint data passed to `save_checkpoint`
   - Verify `records_generated` matches actual progress
   - Verify `tokens_used` is tracked
   - Verify `current_batch` is correct

5. **Test batch is saved before exit**
   - Have partial batch (e.g., 37 records when checkpoint interval is 50)
   - Trigger shutdown
   - Verify `save_batch` called with partial batch

6. **Test alarm is set for forced exit**
   - Call `handle_shutdown`
   - Verify `signal.alarm(100)` was called
   - (Use mock to verify)

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_spot_interruption.py`
- [x] SIGTERM handler tested
- [x] Generation loop exit tested
- [x] Checkpoint saving tested
- [x] Partial batch saving tested
- [x] Tests pass: `pytest tests/unit/test_worker_spot_interruption.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_spot_interruption.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker Spot interruption tests

- Test SIGTERM signal handling
- Test graceful shutdown with checkpoint save
- Test partial batch handling
```

---

### Task 5: Test Worker Bedrock API Failures

**Goal:** Test Worker behavior when Bedrock API calls fail.

**Files to Create:**
- `tests/unit/test_worker_bedrock_errors.py`

**Prerequisites:**
- Task 4 complete (Worker test patterns)

**Implementation Steps:**

1. **Mock Bedrock client**
   - Mock `bedrock_client.invoke_model`
   - Configure to raise various errors

2. **Test Bedrock rate limiting (ThrottlingException)**
   - Mock Bedrock to raise throttling error
   - Verify worker handles gracefully
   - Verify error is logged
   - Note: Current implementation continues to next record

3. **Test Bedrock model error**
   - Mock to raise `ModelErrorException`
   - Verify worker logs error
   - Verify generation continues (doesn't fail entire job)

4. **Test Bedrock timeout**
   - Mock to raise timeout/connection error
   - Verify appropriate handling

5. **Test Bedrock validation error**
   - Mock to raise `ValidationException` (bad prompt)
   - Verify error logged with context
   - Verify job continues

6. **Test Bedrock access denied**
   - Mock to raise `AccessDeniedException`
   - This is a fatal error - verify job fails appropriately

7. **Test partial Bedrock failure**
   - Configure mock to fail on specific records (e.g., every 5th)
   - Run generation for 20 records
   - Verify ~16 records generated (4 failures skipped)
   - Verify all failures logged

8. **Test template_engine.execute_template errors**
   - Mock template engine to raise exception
   - Verify error is caught and logged
   - Verify generation continues

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_bedrock_errors.py`
- [x] Rate limiting tested
- [x] Model errors tested
- [x] Timeout handling tested
- [x] Access denied (fatal) tested
- [x] Partial failure resilience tested
- [x] Tests pass: `pytest tests/unit/test_worker_bedrock_errors.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_bedrock_errors.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker Bedrock error handling tests

- Test rate limiting and throttling
- Test model and validation errors
- Test partial failure resilience
```

---

### Task 6: Test Worker S3 Failures

**Goal:** Test Worker behavior when S3 operations fail.

**Files to Create:**
- `tests/unit/test_worker_s3_errors.py`

**Prerequisites:**
- Task 4 complete

**Implementation Steps:**

1. **Test seed data load failure**
   - Mock S3 `get_object` to raise `NoSuchKey`
   - Call `load_seed_data()`
   - Verify appropriate exception raised
   - Verify job fails (seed data is required)

2. **Test seed data invalid JSON**
   - Mock S3 to return invalid JSON content
   - Verify `JSONDecodeError` is handled
   - Verify meaningful error message

3. **Test checkpoint save failure**
   - Mock S3 `put_object` to raise `ClientError`
   - Call `save_checkpoint()`
   - Verify exception is propagated (checkpoint is critical)

4. **Test batch save failure**
   - Mock S3 `put_object` to fail
   - Call `save_batch()`
   - Verify error is logged
   - Note: Determine if this should fail job or continue

5. **Test export failure**
   - Mock S3 during `export_data()`
   - Verify error handling
   - Verify job status reflects export failure

6. **Test S3 bucket not configured**
   - Remove `BUCKET_NAME` environment variable
   - Verify appropriate error raised early

7. **Test loading batches failure during export**
   - Mock `list_objects_v2` to fail
   - Call `load_all_batches()`
   - Verify returns empty list (fail open)
   - Verify error is logged

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_s3_errors.py`
- [x] Seed data load failures tested
- [x] Checkpoint save failures tested
- [x] Batch save failures tested
- [x] Export failures tested
- [x] Tests pass: `pytest tests/unit/test_worker_s3_errors.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_s3_errors.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker S3 error handling tests

- Test seed data load failures
- Test checkpoint and batch save failures
- Test export operation failures
```

---

### Task 7: Test Worker DynamoDB Failures

**Goal:** Test Worker behavior when DynamoDB operations fail.

**Files to Create:**
- `tests/unit/test_worker_dynamodb_errors.py`

**Prerequisites:**
- Task 4 complete

**Implementation Steps:**

1. **Test job claim race condition**
   - Mock `ConditionalCheckFailedException` on queue update
   - Call `get_next_job()`
   - Verify returns None (job claimed by another worker)
   - Verify no error raised

2. **Test template load failure**
   - Mock `get_item` on templates table to fail
   - Call `load_template()`
   - Verify exception raised
   - Verify job fails

3. **Test template not found**
   - Mock `get_item` to return empty Item
   - Verify `ValueError` raised with "Template not found"

4. **Test job progress update failure**
   - Mock `update_item` on jobs table to fail
   - Call `update_job_progress()`
   - Verify error is logged
   - Verify exception is NOT propagated (non-critical)

5. **Test cost tracking write failure**
   - Mock `put_item` on cost tracking table to fail
   - Call `update_cost_tracking()`
   - Verify error is logged
   - Verify returns cost value (fail open)

6. **Test checkpoint metadata version conflict**
   - Mock `ConditionalCheckFailedException`
   - Call `save_checkpoint()`
   - Verify retry logic executes
   - Verify merge strategy (max records_generated)

7. **Test max retries exceeded on checkpoint**
   - Mock persistent `ConditionalCheckFailedException`
   - Call `save_checkpoint()` (will retry 3 times)
   - Verify exception raised after max retries

8. **Test mark_job_complete failure**
   - Mock queue table operations to fail
   - Call `mark_job_complete()`
   - Verify jobs table is still updated
   - Verify error is logged (not fatal)

9. **Test mark_job_failed with error truncation**
   - Pass very long error message (>1000 chars)
   - Verify message is truncated to 1000 chars

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_dynamodb_errors.py`
- [x] Race conditions tested
- [x] Template load failures tested
- [x] Progress update failures tested (non-critical)
- [x] Checkpoint version conflicts tested
- [x] Job status update failures tested
- [x] Tests pass: `pytest tests/unit/test_worker_dynamodb_errors.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_dynamodb_errors.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker DynamoDB error handling tests

- Test job claim race conditions
- Test checkpoint version conflicts with retry
- Test critical vs non-critical failure handling
```

---

### Task 8: Test Worker Budget Enforcement

**Goal:** Test that Worker correctly enforces budget limits and handles BudgetExceededError.

**Files to Create:**
- `tests/unit/test_worker_budget.py`

**Prerequisites:**
- Task 4 complete

**Implementation Steps:**

1. **Test budget check before each record**
   - Mock `calculate_current_cost` to return specific values
   - Set budget_limit to $10
   - Return $5 for first 5 records, then $11
   - Verify generation stops at budget limit

2. **Test BudgetExceededError raises correctly**
   - Configure cost to exceed budget
   - Verify `BudgetExceededError` is raised
   - Verify error message includes budget amount

3. **Test mark_job_budget_exceeded called**
   - Trigger budget exceeded
   - Verify `mark_job_budget_exceeded` is called
   - Verify job status set to `BUDGET_EXCEEDED`

4. **Test budget with string value (DynamoDB)**
   - Pass `budget_limit` as string "100.0"
   - Verify it's converted to float correctly

5. **Test invalid budget value fallback**
   - Pass invalid budget_limit (None, "invalid")
   - Verify default of 100.0 is used
   - Verify warning is logged

6. **Test cost calculation query failure**
   - Mock `calculate_current_cost` to fail
   - Verify returns 0.0 (fail open)
   - Verify generation continues

7. **Test budget exactly at limit**
   - Set cost exactly equal to budget
   - Verify budget exceeded (>= comparison)

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_budget.py`
- [x] Budget enforcement before each record tested
- [x] BudgetExceededError handling tested
- [x] Job status update tested
- [x] Edge cases (string values, invalid values) tested
- [x] Tests pass: `pytest tests/unit/test_worker_budget.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_budget.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker budget enforcement tests

- Test budget limit checking
- Test BudgetExceededError handling
- Test edge cases with invalid budget values
```

---

### Task 9: Test Worker Checkpoint Recovery

**Goal:** Test that Worker correctly resumes from checkpoints after interruption.

**Files to Create:**
- `tests/unit/test_worker_checkpoint_recovery.py`

**Prerequisites:**
- Tasks 4, 6, 7 complete

**Implementation Steps:**

1. **Test load checkpoint from S3**
   - Mock S3 with existing checkpoint data
   - Mock DynamoDB metadata with version
   - Call `load_checkpoint()`
   - Verify returned data matches stored checkpoint
   - Verify `_version` is populated

2. **Test load checkpoint when none exists**
   - Mock S3 to raise `NoSuchKey`
   - Call `load_checkpoint()`
   - Verify returns default checkpoint structure
   - Verify `records_generated: 0`

3. **Test generation resumes from checkpoint**
   - Set checkpoint with `records_generated: 50`
   - Start generation for 100 records
   - Verify Bedrock called only 50 times (records 50-99)
   - Verify batch numbering continues correctly

4. **Test checkpoint version increments**
   - Start with version 5
   - Save checkpoint
   - Verify new version is 6

5. **Test checkpoint S3 + DynamoDB consistency**
   - Save checkpoint
   - Verify DynamoDB metadata updated first
   - Verify S3 blob updated second
   - Verify version matches in both

6. **Test checkpoint with existing batches**
   - Set checkpoint with `current_batch: 3`
   - Save new batch
   - Verify batch number is 3 (not 1)

7. **Test corrupted checkpoint recovery**
   - Mock S3 to return invalid JSON
   - Verify error logged
   - Verify returns default checkpoint (fail safe)

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_checkpoint.py`
- [x] Checkpoint loading tested
- [x] Resume from checkpoint tested
- [x] Version management tested
- [x] Corrupted checkpoint handling tested
- [x] Tests pass: `pytest tests/unit/test_worker_checkpoint.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_checkpoint_recovery.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker checkpoint recovery tests

- Test checkpoint load and save
- Test generation resume from checkpoint
- Test version management
- Test corrupted checkpoint handling
```

---

### Task 10: Test Worker Export Formats

**Goal:** Test that Worker correctly exports data in all supported formats.

**Files to Create:**
- `tests/unit/test_worker_export.py`

**Prerequisites:**
- Task 6 complete (S3 mocking)

**Implementation Steps:**

1. **Test JSONL export**
   - Generate sample records
   - Call `export_jsonl()`
   - Verify S3 put_object called with correct key
   - Verify content is valid JSONL (one JSON per line)

2. **Test Parquet export**
   - Generate sample records
   - Call `export_parquet()`
   - Verify S3 put_object called
   - Verify content type is octet-stream
   - (Optionally verify Parquet structure if practical)

3. **Test CSV export**
   - Generate sample records
   - Call `export_csv()`
   - Verify S3 put_object called
   - Verify content is valid CSV with headers

4. **Test multiple format export**
   - Set `output_format: ['JSONL', 'PARQUET']`
   - Call `export_data()`
   - Verify both formats exported

5. **Test partition_strategy: timestamp (JSONL)**
   - Set `partition_strategy: 'timestamp'`
   - Generate records with different dates
   - Verify partitioned keys like `date=2025-01-01/records.jsonl`

6. **Test partition_strategy unsupported warning**
   - Set partition_strategy on Parquet export
   - Verify warning logged
   - Verify falls back to single file

7. **Test export with empty records**
   - Call `export_data()` with no records
   - Verify warning logged
   - Verify no S3 writes attempted

8. **Test nested JSON serialization in Parquet**
   - Include nested `generation_result` in records
   - Export to Parquet
   - Verify nested data is JSON-serialized string

**Verification Checklist:**
- [x] Test file exists at `tests/unit/test_worker_export.py`
- [x] JSONL export tested
- [x] Parquet export tested
- [x] CSV export tested
- [x] Multiple format export tested
- [x] Partition strategy tested
- [x] Empty records handling tested
- [x] Tests pass: `pytest tests/unit/test_worker_export.py -v`

**Testing Instructions:**
```bash
PYTHONPATH=. pytest tests/unit/test_worker_export.py -v
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(backend): add Worker export format tests

- Test JSONL, Parquet, CSV exports
- Test multiple format exports
- Test partition strategies
- Test edge cases
```

---

## Phase Verification

**How to verify Phase 2 is complete:**

1. **Run all backend tests:**
   ```bash
   PYTHONPATH=. pytest tests/unit tests/integration -v
   ```
   - All tests should pass
   - No AWS credentials required

2. **Run specific new test files:**
   ```bash
   PYTHONPATH=. pytest tests/unit/test_lambda_*.py tests/unit/test_worker_*.py -v
   ```

3. **Check coverage (optional):**
   ```bash
   PYTHONPATH=. pytest tests/unit --cov=backend --cov-report=term-missing
   ```
   - Lambda handlers: ~80%+ coverage
   - Worker: ~80%+ coverage

4. **Verify in CI:**
   ```bash
   npm run check
   ```
   - All linting passes
   - All tests pass

**Integration Points:**
- Uses fixtures from Phase 0
- Follows patterns established in Phase 1

**Known Limitations:**
- Bedrock response mocking is simplified (no actual model behavior)
- moto may not perfectly replicate all AWS error conditions
- Some edge cases in ECS task management not tested (complex to mock)

**Technical Debt:**
- Download functionality in frontend has TODO - tests document current state
- cancelJob and deleteJob share endpoint - tests document this behavior
- Some DynamoDB error codes may not be exhaustively tested
