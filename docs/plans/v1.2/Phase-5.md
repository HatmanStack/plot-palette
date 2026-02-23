# Phase 5: Output Quality Scoring

## Phase Goal

Build an automated quality evaluation pipeline that scores generated data after a job completes. The system samples records from a completed job's output, sends them to an LLM with a structured scoring prompt, stores the resulting quality metrics, and displays a quality report on the JobDetail page. This closes the feedback loop — users can now compare output quality across model tiers, template versions, and prompt strategies.

**Success criteria:**
- Quality scoring is triggered automatically after job completion (via Step Functions)
- A configurable sample of output records is evaluated on coherence, relevance, diversity, and format compliance
- Quality metrics are stored in a new DynamoDB table and displayed on the JobDetail page
- Batch comparison view shows quality scores side-by-side
- All new code has unit tests; coverage remains above 70%

**Estimated tokens:** ~40,000

---

## Prerequisites

- Phase 4 complete (batch jobs provide the A/B testing context where quality scoring is most valuable)
- Understanding of the Step Functions state machine and its terminal states
- Understanding of the worker's export flow (output files at `jobs/{job_id}/exports/dataset.{ext}`)
- Understanding of Bedrock model invocation patterns in `backend/ecs_tasks/worker/template_engine.py` (note: this file lives in the worker package, not in `shared/`)

---

## Task 1: Quality Metrics Data Model + Table

**Goal:** Define the quality metrics entity model and DynamoDB table for storing per-job quality scores.

**Files to Modify/Create:**
- `backend/shared/models.py` — New `QualityMetrics` and `RecordScore` Pydantic models
- `backend/shared/constants.py` — Quality-related constants
- `backend/template.yaml` — New DynamoDB table
- `tests/unit/test_shared.py` — Model tests

**Implementation Steps:**

1. **New Pydantic models:**
   ```python
   class RecordScore(BaseModel):
       record_index: int
       coherence: float  # 0.0-1.0
       relevance: float  # 0.0-1.0
       format_compliance: float  # 0.0-1.0
       detail: str  # Brief rationale from the scoring LLM

   class QualityMetrics(BaseModel):
       job_id: str
       scored_at: datetime
       sample_size: int
       total_records: int
       model_used_for_scoring: str  # Which LLM did the scoring
       aggregate_scores: dict[str, float]  # {coherence: 0.85, relevance: 0.92, ...}
       diversity_score: float  # 0.0-1.0 (computed from record similarity)
       overall_score: float  # Weighted average of all dimensions
       record_scores: list[RecordScore]  # Per-record detail
       scoring_cost: float  # USD cost of the scoring LLM calls
       status: str  # "PENDING", "SCORING", "COMPLETED", "FAILED"
       error_message: str | None = None
   ```
   Add `to_table_item()` and `from_dynamodb()` methods.

2. **New constants:**
   - `QUALITY_SAMPLE_SIZE = 20` — Default records to sample for scoring
   - `QUALITY_MAX_SAMPLE = 50` — Maximum allowed sample size
   - `QUALITY_SCORING_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"` — Use premium model for accurate scoring
   - `QUALITY_DIMENSIONS = ["coherence", "relevance", "format_compliance"]`
   - `QUALITY_WEIGHTS = {"coherence": 0.35, "relevance": 0.35, "format_compliance": 0.15, "diversity": 0.15}`
   - `QualityStatus` enum: `PENDING`, `SCORING`, `COMPLETED`, `FAILED`

3. **New DynamoDB table:**
   - Name: `plot-palette-QualityMetrics-${Environment}`
   - PK: `job_id` (S) — One quality report per job
   - PAY_PER_REQUEST, PITR enabled
   - TTL on `ttl` attribute (90 days, same as cost tracking)

**Verification Checklist:**
- [x] QualityMetrics model serializes/deserializes correctly
- [x] RecordScore validates score ranges (0.0-1.0)
- [x] QualityStatus enum has all 4 values
- [x] Table has correct PK and TTL

**Testing Instructions:**

Add to `tests/unit/test_shared.py`:
```python
# 1. test_quality_metrics_creation — Create QualityMetrics, assert all fields.
# 2. test_quality_metrics_to_dynamodb — Serialize, verify format.
# 3. test_record_score_validation — Score > 1.0 raises ValidationError.
# 4. test_quality_metrics_overall_score — Verify weighted average calculation.
```

**Commit Message Template:**
```
feat(shared): add QualityMetrics model and DynamoDB table

- QualityMetrics and RecordScore Pydantic models
- Quality scoring constants and dimensions
- QualityMetrics table with 90-day TTL
```

---

## Task 2: Quality Scoring Lambda

**Goal:** Create the Lambda function that samples records from a completed job, sends them to an LLM for evaluation, computes aggregate scores, and stores results.

**Files to Modify/Create:**
- `backend/lambdas/quality/` — New directory (create with `__init__.py`)
- `backend/lambdas/quality/score_job.py` — New Lambda handler
- `backend/template.yaml` — New function resource
- `tests/unit/test_score_job.py` — Unit tests

**Prerequisites:**
- Task 1 complete (QualityMetrics model and table exist)
- Understanding of Bedrock invocation patterns

**Implementation Steps:**

1. **Create the `backend/lambdas/quality/` directory:**
   - `mkdir -p backend/lambdas/quality && touch backend/lambdas/quality/__init__.py`
   - All Lambda subdirectories require `__init__.py` to match the existing pattern.

2. **`score_job.py` handler:**
   - Invocation: Step Functions (after MarkJobCompleted) or API Gateway (manual trigger)
   - Input from SFN: `{ "job_id": str }`
   - Input from API: standard event with `pathParameters.job_id`
   - Logic:
     a. Fetch job from Jobs table — verify COMPLETED status
     b. Create PENDING quality metrics record in QualityMetrics table
     c. Update to SCORING status
     d. Load the export file from S3: `jobs/{job_id}/exports/dataset.{format}`
        - For JSONL: read lines, parse JSON
        - For CSV/Parquet: not supported for quality scoring (return error suggesting JSONL)
     e. Sample `min(QUALITY_SAMPLE_SIZE, total_records)` random records
     f. Fetch the template used (from job config.template_id + config.template_version) to understand expected output format
     g. For each sampled record, build a scoring prompt and call Bedrock:
        ```
        You are evaluating the quality of a synthetically generated data record.

        Template context: This template generates {template.name} data.
        Schema requirements: {schema_requirements}
        Seed data used: {record.seed_data_id}

        Generated record:
        {record.generation_result}

        Score this record on the following dimensions (0.0 to 1.0):
        1. Coherence: Is the text grammatically correct, logically consistent, and well-structured?
        2. Relevance: Does the output relate to the seed data and follow the template's intent?
        3. Format compliance: Does the output structure match the expected schema?

        Respond in JSON only:
        {"coherence": 0.X, "relevance": 0.X, "format_compliance": 0.X, "detail": "brief rationale"}
        ```
     h. Parse each scoring response as JSON (with markdown stripping, same as seed generation)
     i. Compute diversity score:
        - Simple approach: count unique first-50-chars across all sampled records
        - Diversity = unique_prefixes / sample_size
     j. Compute aggregate scores: mean of each dimension across all records
     k. Compute overall score: weighted average using QUALITY_WEIGHTS
     l. Store QualityMetrics record with COMPLETED status
     m. Track scoring cost (tokens used * model pricing)
   - Lambda timeout: 120 seconds (multiple Bedrock calls for 20+ records)
   - Lambda memory: 1024 MB

3. **Error handling:**
   - If Bedrock call fails for a single record: score that record as `null`, exclude from aggregates
   - If more than 50% of records fail scoring: mark quality metrics as FAILED
   - If export file doesn't exist or is empty: mark as FAILED with error message

4. **Batching optimization:**
   - Instead of one Bedrock call per record, batch 5 records into a single prompt
   - This reduces API calls from 20 to 4 and reduces cost
   - Prompt format: "Score the following 5 records..." with numbered records
   - Parse response as JSON array of score objects

**Verification Checklist:**
- [x] Samples correct number of records (min of QUALITY_SAMPLE_SIZE and total)
- [x] Sends scoring prompts to Bedrock
- [x] Parses scoring responses correctly
- [x] Computes aggregate scores as mean across records
- [x] Diversity score calculated from unique prefixes
- [x] Overall score is weighted average
- [x] Handles partial scoring failures gracefully
- [x] Stores COMPLETED or FAILED status
- [x] Tracks and reports scoring cost

**Testing Instructions:**

Write tests in `tests/unit/test_score_job.py`:
```python
# 1. test_score_job_success — Mock S3 export with 50 records, mock Bedrock scoring responses. Assert QualityMetrics stored with correct aggregates.
# 2. test_score_job_samples_correctly — 1000 records, sample_size=20. Assert only 20 scoring calls.
# 3. test_score_job_diversity_calculation — 20 records, 15 unique prefixes. Assert diversity=0.75.
# 4. test_score_job_partial_failure — 3 of 20 scoring calls fail. Assert aggregates from 17 records.
# 5. test_score_job_majority_failure — 15 of 20 fail. Assert FAILED status.
# 6. test_score_job_not_completed — Job status is RUNNING. Assert error.
# 7. test_score_job_no_export — S3 file doesn't exist. Assert FAILED with error message.
# 8. test_score_job_batched_prompts — Assert Bedrock called 4 times (5 records per batch) not 20.
# 9. test_score_job_cost_tracking — Assert scoring_cost calculated from token usage.
```

**Commit Message Template:**
```
feat(lambdas): add automated quality scoring for completed jobs

- Samples records and scores via Bedrock LLM
- Coherence, relevance, format compliance, diversity dimensions
- Batched scoring prompts (5 records per call)
- Weighted overall score with cost tracking
```

---

## Task 3: Quality Scoring API Endpoints

**Goal:** Create endpoints to retrieve quality metrics and trigger manual scoring.

**Files to Modify/Create:**
- `backend/lambdas/quality/get_quality.py` — New Lambda handler
- `backend/lambdas/quality/trigger_scoring.py` — New Lambda handler
- `backend/template.yaml` — New function resources + API routes
- `tests/unit/test_quality_api.py` — Unit tests

**Implementation Steps:**

1. **`get_quality.py` handler:**
   - Route: `GET /jobs/{job_id}/quality`
   - Fetch QualityMetrics from table by `job_id`
   - Verify job ownership (fetch job, check user_id)
   - Return full quality metrics or 404 if not scored yet
   - Response includes: aggregate_scores, diversity_score, overall_score, sample_size, scoring_cost, record_scores (detailed per-record data), status

2. **`trigger_scoring.py` handler:**
   - Route: `POST /jobs/{job_id}/quality`
   - Request body (optional): `{ "sample_size": 30 }` to override default
   - Verify job is COMPLETED and owned by user
   - Check if quality metrics already exist (if COMPLETED, return 409)
   - Invoke score_job Lambda asynchronously (InvocationType='Event')
   - Return 202 Accepted: `{ message: "Quality scoring started", job_id }`

**Verification Checklist:**
- [x] GET returns quality metrics for scored job
- [x] GET returns 404 for unscored job
- [x] POST triggers scoring asynchronously
- [x] POST returns 409 if already scored
- [x] POST returns 400 if job not COMPLETED
- [x] Ownership verified on both endpoints

**Testing Instructions:**

Write tests in `tests/unit/test_quality_api.py`:
```python
# 1. test_get_quality_success — Mock scored job. Assert full metrics returned.
# 2. test_get_quality_not_scored — No metrics exist. Assert 404.
# 3. test_trigger_scoring_success — Mock COMPLETED job. Assert 202, Lambda invoked async.
# 4. test_trigger_scoring_already_scored — Metrics exist with COMPLETED status. Assert 409.
# 5. test_trigger_scoring_not_completed — Job is RUNNING. Assert 400.
# 6. test_get_quality_not_owner — Different user. Assert 403.
```

**Commit Message Template:**
```
feat(lambdas): add quality metrics retrieval and manual scoring trigger

- GET /jobs/{id}/quality returns scoring results
- POST /jobs/{id}/quality triggers async scoring
- 409 if already scored, 400 if job not completed
```

---

## Task 4: Quality Report — Frontend

**Goal:** Display quality scoring results on the JobDetail page and add quality columns to the batch comparison table.

**Files to Modify/Create:**
- `frontend/src/services/api.ts` — New API functions + Zod schemas
- `frontend/src/components/QualityReport.tsx` — New component
- `frontend/src/components/QualityScoreBar.tsx` — Reusable score visualization
- `frontend/src/routes/JobDetail.tsx` — Integrate quality report
- `frontend/src/routes/BatchDetail.tsx` — Add quality column
- `frontend/src/components/QualityReport.test.tsx` — Tests
- `frontend/src/components/QualityScoreBar.test.tsx` — Tests

**Prerequisites:**
- Tasks 2-3 complete (scoring Lambda and API exist)
- Phase 4 complete (BatchDetail page exists)

**Implementation Steps:**

1. **API service additions:**
   - `fetchQualityMetrics(jobId: string): Promise<QualityMetrics | null>`
   - `triggerQualityScoring(jobId: string, sampleSize?: number): Promise<void>`
   - Zod schemas for `QualityMetrics` and `RecordScore`

2. **QualityScoreBar component:**
   - Props: `{ score: number, label: string, size?: 'sm' | 'md' }` — score is 0.0-1.0
   - Renders a horizontal bar filled to `score * 100%`
   - Color coding: green (>= 0.8), yellow (>= 0.6), red (< 0.6)
   - Shows numeric value: "0.85"
   - Small variant for table cells, medium for report

3. **QualityReport component:**
   - Props: `{ jobId: string }`
   - Uses `useQuery({ queryKey: ['quality', jobId] })` to fetch metrics
   - States:
     - **Not scored:** Show "Run Quality Check" button
     - **Scoring in progress:** Show spinner + "Scoring... (this may take a minute)"
     - **Completed:** Show full report
     - **Failed:** Show error message + "Retry" button
   - Report layout:
     - **Overall Score** — Large number with QualityScoreBar
     - **Dimension Breakdown** — 4 QualityScoreBars (coherence, relevance, format_compliance, diversity)
     - **Sample Details** — Expandable section showing per-record scores with rationale
     - **Metadata** — Sample size, scoring cost, model used, scored_at timestamp
   - Poll while status is SCORING (5s interval, stop when COMPLETED or FAILED)

4. **JobDetail integration:**
   - Add QualityReport section below cost breakdown (only for COMPLETED jobs)
   - Uses lazy loading: don't fetch quality data until user scrolls to section or component mounts

5. **BatchDetail integration:**
   - Add "Quality" column to BatchJobTable
   - For each job: show overall_score with QualityScoreBar (small variant)
   - If not scored: show "—" or "Score" button
   - Sort by quality column enables comparing model tier quality

**Verification Checklist:**
- [x] Quality report shows all dimensions with score bars
- [x] "Run Quality Check" button triggers scoring
- [x] Loading state during scoring
- [x] Per-record detail is expandable
- [x] Scoring cost displayed
- [x] Batch table shows quality column
- [x] Color coding matches score thresholds
- [x] Polling stops when scoring completes

**Testing Instructions:**

Create `frontend/src/components/QualityScoreBar.test.tsx`:
```typescript
// 1. test: renders bar with correct fill percentage
// 2. test: green color for score >= 0.8
// 3. test: yellow color for score >= 0.6
// 4. test: red color for score < 0.6
// 5. test: shows numeric score label
```

Create `frontend/src/components/QualityReport.test.tsx`:
```typescript
// 6. test: shows "Run Quality Check" for unscored job
// 7. test: shows scoring progress state
// 8. test: shows completed report with all dimensions
// 9. test: shows per-record scores in expandable section
// 10. test: triggers scoring when button clicked
// 11. test: shows failed state with retry button
```

**Commit Message Template:**
```
feat(frontend): add quality scoring report to job and batch views

- QualityReport component with dimension bars and record details
- QualityScoreBar reusable visualization (green/yellow/red)
- JobDetail integration with lazy loading
- BatchDetail quality column for comparison
```

---

## Task 5: Step Functions Integration

**Goal:** Add automatic quality scoring as a step in the Step Functions state machine, triggered after job completion.

**Files to Modify/Create:**
- `backend/infrastructure/step-functions/job-lifecycle.asl.json` — Add scoring state
- `backend/template.yaml` — Add `${ScoreJobFunctionArn}` substitution variable for ASL
- `tests/unit/test_step_functions_scoring.py` — Verify state machine structure

**Prerequisites:**
- Task 2 complete (score_job Lambda exists)
- Phase 3 complete (notification states already exist in ASL — scoring inserts before them)

**Implementation Steps:**

1. **State machine update in `backend/infrastructure/step-functions/job-lifecycle.asl.json`:**

   The state machine is defined in JSON (ASL format), NOT in `backend/template.yaml`. The template.yaml references this file and passes substitution variables.

   After Phase 3, the flow for completed jobs is: `MarkJobCompleted` → `SendNotificationCompleted` → `EndCompleted`. Insert quality scoring between completion and notification so the notification can include the quality score.

   **Change `MarkJobCompleted`** to point to scoring instead of notification:
   ```json
   "MarkJobCompleted": {
     ...
     "Next": "ScoreJobQuality"
   }
   ```

   **Add `ScoreJobQuality` state:**
   ```json
   "ScoreJobQuality": {
     "Type": "Task",
     "Resource": "${ScoreJobFunctionArn}",
     "Parameters": {
       "job_id.$": "$.job_id"
     },
     "ResultPath": null,
     "TimeoutSeconds": 180,
     "Catch": [
       {
         "ErrorEquals": ["States.ALL"],
         "ResultPath": null,
         "Next": "SendNotificationCompleted"
       }
     ],
     "Next": "SendNotificationCompleted"
   }
   ```

   The resulting flow: `MarkJobCompleted` → `ScoreJobQuality` → `SendNotificationCompleted` → `EndCompleted`

   - Quality scoring is best-effort: Catch all errors and proceed to notification
   - Only triggered for COMPLETED jobs (not FAILED or BUDGET_EXCEEDED)
   - Timeout of 180s (scoring Lambda has 120s timeout + buffer)

2. **Add `${ScoreJobFunctionArn}` substitution** to the state machine definition in `backend/template.yaml` where it passes substitutions to the ASL file.

**Verification Checklist:**
- [ ] `ScoreJobQuality` state added to `job-lifecycle.asl.json` (not template.yaml)
- [ ] State references `${ScoreJobFunctionArn}` (substituted by SAM template)
- [ ] Catch block handles all errors (quality failure doesn't fail the job)
- [ ] ResultPath: null (don't pollute state with scoring output)
- [ ] Timeout is 180 seconds
- [ ] Flow order: MarkJobCompleted → ScoreJobQuality → SendNotificationCompleted → EndCompleted
- [ ] `cfn-lint backend/template.yaml` passes

**Testing Instructions:**

Verify structure:
```bash
cd backend && cfn-lint template.yaml
```

Write a test to verify state machine definition includes the scoring step:
```python
# test_step_functions_scoring.py
# Parse backend/infrastructure/step-functions/job-lifecycle.asl.json
# Assert ScoreJobQuality state exists
# Assert MarkJobCompleted.Next == "ScoreJobQuality"
# Assert ScoreJobQuality.Next == "SendNotificationCompleted"
# Assert Catch block present
```

**Commit Message Template:**
```
feat(infra): add quality scoring step to job lifecycle state machine

- ScoreJobQuality runs after MarkJobCompleted
- Best-effort with Catch all errors
- Notification step moved after scoring
```

---

## Task 6: Infrastructure Updates for Phase 5

**Goal:** Add all remaining SAM resources for quality scoring.

**Files to Modify/Create:**
- `backend/template.yaml` — New table, functions, routes, permissions

**Implementation Steps:**

1. **QualityMetrics table:**
   - Name: `plot-palette-QualityMetrics-${Environment}`
   - PK: `job_id` (S)
   - PAY_PER_REQUEST, PITR enabled
   - TTL on `ttl` attribute

2. **New Lambda functions:**
   - `ScoreJobFunction`: No API route (SFN-invoked + async), 1024MB, 120s, DynamoDB (Jobs, Templates, QualityMetrics), S3 read, Bedrock InvokeModel
   - `GetQualityFunction`: `GET /jobs/{job_id}/quality`, 256MB, 15s, DynamoDB read (Jobs, QualityMetrics)
   - `TriggerScoringFunction`: `POST /jobs/{job_id}/quality`, 256MB, 15s, DynamoDB read (Jobs, QualityMetrics), Lambda InvokeFunction (async invoke of ScoreJobFunction)

3. **Add `QUALITY_METRICS_TABLE_NAME` to Globals environment.**

4. **Permissions:**
   - ScoreJobFunction needs: Bedrock InvokeModel, S3 GetObject, DynamoDB read/write
   - TriggerScoringFunction needs: Lambda InvokeFunction on ScoreJobFunction ARN

**Verification Checklist:**
- [ ] `cfn-lint backend/template.yaml` passes
- [ ] All functions have correct timeouts and memory
- [ ] Bedrock permissions granted
- [ ] Lambda invoke permissions for trigger → scorer
- [ ] State machine references correct function ARN

**Commit Message Template:**
```
feat(infra): add quality scoring SAM resources

- QualityMetrics DynamoDB table with TTL
- ScoreJob, GetQuality, TriggerScoring Lambda functions
- Bedrock and Lambda invoke permissions
```

---

## Task 7: Integration Tests for Phase 5

**Goal:** Integration tests for the quality scoring pipeline.

**Files to Modify/Create:**
- `tests/integration/test_quality_scoring.py` — Integration tests

**Implementation Steps:**

1. **End-to-end scoring integration test:**
   - Create Jobs, Templates, and QualityMetrics tables with moto
   - Create S3 bucket with moto
   - Insert a COMPLETED job and its template
   - Upload a JSONL export file with 50 records to the correct S3 path
   - Mock Bedrock client to return valid JSON scoring responses
   - Invoke score_job handler
   - Assert QualityMetrics record created with correct aggregate scores
   - Assert sample_size matches expected value
   - Assert scoring_cost calculated

2. **API endpoint integration tests:**
   - Insert quality metrics record
   - Invoke get_quality handler — assert full metrics returned
   - Invoke trigger_scoring on already-scored job — assert 409

**Verification Checklist:**
- [ ] Scoring pipeline reads export from S3
- [ ] Scoring results stored in QualityMetrics table
- [ ] Aggregate scores are means of per-record scores
- [ ] GET endpoint returns stored metrics
- [ ] Trigger endpoint rejects already-scored jobs

**Commit Message Template:**
```
test(integration): add quality scoring pipeline integration tests

- End-to-end: S3 export -> Bedrock scoring -> DynamoDB storage
- API: get metrics, trigger rejection on duplicate
```

---

## Phase Verification

After completing all tasks in Phase 5:

### Backend Verification
```bash
PYTHONPATH=. pytest tests/unit tests/integration -v --tb=short --cov=backend --cov-report=term-missing --cov-fail-under=70
cd backend && uvx ruff check .
cd backend && cfn-lint template.yaml
```

### Frontend Verification
```bash
cd frontend && npx vitest run --coverage
cd frontend && npm run lint
```

### Full Check
```bash
npm run check
```

### Known Limitations
- Quality scoring uses Claude Sonnet (tier-3) for accuracy, which costs ~$18/M tokens. Scoring 20 records costs roughly $0.05-$0.15 depending on record length.
- Diversity score is simplistic (unique prefix ratio). Future: use embedding similarity for true diversity measurement.
- Quality scoring only works on JSONL exports. CSV and Parquet jobs would need conversion.
- Scoring is one-shot (no re-scoring with different criteria). To re-score, delete the quality metrics record first.
- LLM-as-judge has known biases (prefers verbose outputs, may rate its own model's output higher). Consider cross-model scoring in the future.

### Future Enhancements (Out of Scope)
- Custom scoring rubrics (user-defined dimensions and weights)
- Embedding-based diversity scoring (OpenSearch or pgvector)
- Quality trend tracking across template versions
- Auto-reject low-quality records and re-generate
- Quality-gated batch workflows (only proceed if score > threshold)

---

## All Phases Complete

After Phase 5, the platform supports:

1. **Data Generation** — Jobs with checkpoint recovery, multi-model support
2. **Partial Export** — Download results mid-job
3. **Template Management** — Version history, diff view, marketplace, forking
4. **Cost Visibility** — Analytics dashboard, per-model breakdown
5. **Notifications** — Email + webhook on job events
6. **Real-Time Progress** — SSE streaming replaces polling
7. **Batch Experimentation** — Parameter sweeps for A/B testing
8. **Seed Bootstrapping** — Auto-generate seed data from schema
9. **Quality Feedback** — Automated scoring with LLM-as-judge

`PLAN_COMPLETE`
