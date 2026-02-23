# Phase 4: Batch Job Creation + Seed Data Generation from Schema

## Phase Goal

Build two features that scale the platform from single-job workflows to experimentation. **Batch Job Creation** lets users launch multiple jobs in one action — same template across model tiers, same model across seed data files, or parameter sweeps for A/B testing. **Seed Data Generation from Schema** eliminates the cold start problem by auto-generating seed data from a template's schema requirements using a Bedrock LLM call.

**Success criteria:**
- Users can create a batch of jobs from a single configuration with parameter sweeps
- A BatchDetail page shows all jobs in a batch with comparative stats
- Users can generate seed data from a template's schema requirements without uploading a file
- Generated seed data is validated and stored in S3 ready for job creation
- All new code has unit tests; coverage remains above 70%

**Estimated tokens:** ~50,000

---

## Prerequisites

- Phase 3 complete (notifications work — batch completion notifications will use them)
- Understanding of the existing `create_job.py` flow (validates template, starts SFN)
- Understanding of `schema_requirements` field on templates (extracted from `{{ variable.path }}` in prompts)
- Understanding of `validate_seed_data.py` Lambda (validates data against schema)

---

## Task 1: Batch Data Model + Table

**Goal:** Define the Batch entity model and DynamoDB table for tracking batches of jobs.

**Files to Modify/Create:**
- `backend/shared/models.py` — New `BatchConfig` Pydantic model
- `backend/shared/constants.py` — New batch-related constants
- `backend/template.yaml` — New DynamoDB table
- `tests/unit/test_shared.py` — Model tests

**Prerequisites:**
- Understanding of existing model patterns in `shared/models.py`

**Implementation Steps:**

1. **New Pydantic model:**
   ```python
   class BatchConfig(BaseModel):
       batch_id: str
       user_id: str
       name: str  # User-provided batch name
       status: str  # "PENDING", "RUNNING", "COMPLETED", "PARTIAL_FAILURE"
       created_at: datetime
       updated_at: datetime
       job_ids: list[str]  # References to individual jobs
       total_jobs: int
       completed_jobs: int = 0
       failed_jobs: int = 0
       template_id: str
       template_version: int
       sweep_config: dict[str, Any]  # What was varied (model_tiers, seed_data_paths, etc.)
       total_cost: float = 0.0
   ```
   Add `to_table_item()` and `from_dynamodb()` methods.

2. **New constants:**
   - `BatchStatus` enum: `PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL_FAILURE`
   - `MAX_BATCH_SIZE = 20` — Maximum jobs per batch
   - Add `"batches"` entry to `TABLE_NAMES` dict

3. **New DynamoDB table:**
   - Name: `plot-palette-Batches-${Environment}`
   - PK: `batch_id` (S)
   - GSI: `user-id-index` (PK: `user_id`, SK: `created_at`)
   - PAY_PER_REQUEST, PITR enabled

**Verification Checklist:**
- [x] BatchConfig model serializes/deserializes correctly
- [x] BatchStatus enum has all 4 states
- [x] Table has correct PK and GSI
- [x] Model handles empty job_ids list

**Testing Instructions:**

Add to `tests/unit/test_shared.py`:
```python
# 1. test_batch_config_creation — Create BatchConfig, assert all fields.
# 2. test_batch_config_to_dynamodb — Serialize, verify DynamoDB format.
# 3. test_batch_config_from_dynamodb — Deserialize, verify model fields.
# 4. test_batch_status_enum — Verify all 4 values exist.
```

**Commit Message Template:**
```
feat(shared): add BatchConfig model and Batches DynamoDB table

- BatchConfig Pydantic model with serialization
- BatchStatus enum (PENDING, RUNNING, COMPLETED, PARTIAL_FAILURE)
- Batches table with user-id-index GSI
```

---

## Task 2: Batch Creation Endpoint — Backend

**Goal:** Create a Lambda endpoint that accepts a batch configuration, fans out to individual job creation, and returns a batch ID for tracking.

**Files to Modify/Create:**
- `backend/lambdas/jobs/create_batch.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_create_batch.py` — Unit tests

**Prerequisites:**
- Task 1 complete (BatchConfig model and table exist)
- Understanding of create_job.py flow

**Implementation Steps:**

1. **`create_batch.py` handler:**
   - Route: `POST /jobs/batch`
   - Request body:
     ```json
     {
       "name": "A/B test: model comparison",
       "template_id": "tmpl-123",
       "template_version": 1,
       "seed_data_path": "seed-data/user-123/data.json",
       "base_config": {
         "budget_limit": 10.0,
         "num_records": 100,
         "output_format": "JSONL"
       },
       "sweep": {
         "model_tier": ["tier-1", "tier-2", "tier-3"]
       }
     }
     ```
   - Sweep types supported:
     - `model_tier: [...]` — Run same job with different model tiers
     - `seed_data_path: [...]` — Run with different seed data files
     - `num_records: [...]` — Run with different record counts
     - Only one sweep dimension per batch (simplicity over combinatorial explosion)
   - Logic:
     a. Validate request (template exists, seed data paths valid, budget limits reasonable)
     b. Calculate total jobs: `len(sweep_values)`. Enforce `MAX_BATCH_SIZE`.
     c. Generate `batch_id` via UUID
     d. For each sweep value:
        - Build individual job config (merge base_config with sweep override)
        - Generate `job_id`
        - Store job in Jobs table with `batch_id` in config
        - Start Step Functions execution for each job
     e. Store BatchConfig in Batches table
     f. Return `{ batch_id, job_count, job_ids }`
   - Set Lambda timeout to 60 seconds (fan-out of up to 20 SFN starts)
   - Set Lambda memory to 512 MB

2. **Error handling:**
   - If some jobs fail to create: continue with remaining, mark batch as PARTIAL_FAILURE
   - Return which job_ids succeeded and which failed
   - Store successful job_ids in BatchConfig

**Verification Checklist:**
- [x] Creates individual jobs for each sweep value
- [x] Stores batch record with all job IDs
- [x] Enforces MAX_BATCH_SIZE (20)
- [x] Validates template exists
- [x] Returns batch_id and job_ids
- [x] Handles partial failures (some jobs fail to create)
- [x] Only one sweep dimension allowed
- [x] Individual jobs have batch_id in their config

**Testing Instructions:**

Write tests in `tests/unit/test_create_batch.py`:
```python
# 1. test_batch_create_model_sweep — Sweep 3 model tiers. Assert 3 jobs created, 3 SFN executions started.
# 2. test_batch_create_seed_data_sweep — Sweep 2 seed files. Assert 2 jobs.
# 3. test_batch_exceeds_max_size — 25 sweep values. Assert 400 (exceeds MAX_BATCH_SIZE).
# 4. test_batch_template_not_found — Invalid template_id. Assert 404.
# 5. test_batch_partial_failure — Mock 1 SFN start fails. Assert batch created with 2 of 3 jobs.
# 6. test_batch_stores_sweep_config — Assert sweep_config stored in batch record.
# 7. test_batch_single_sweep_dimension — Assert rejects request with 2 sweep keys.
```

**Commit Message Template:**
```
feat(lambdas): add batch job creation with parameter sweep

- POST /jobs/batch creates multiple jobs from sweep config
- Supports model_tier, seed_data_path, num_records sweeps
- Max 20 jobs per batch
- Partial failure handling
```

---

## Task 3: Batch CRUD Endpoints — Backend

**Goal:** Create endpoints for listing batches, getting batch details, and deleting a batch (cancels all its jobs).

**Files to Modify/Create:**
- `backend/lambdas/jobs/list_batches.py` — New Lambda handler
- `backend/lambdas/jobs/get_batch.py` — New Lambda handler
- `backend/lambdas/jobs/delete_batch.py` — New Lambda handler
- `backend/template.yaml` — New function resources + API routes
- `tests/unit/test_batch_crud.py` — Unit tests

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**

1. **`list_batches.py`:**
   - Route: `GET /jobs/batches`
   - Query Batches table by `user-id-index` GSI
   - Return summary list: batch_id, name, status, total_jobs, completed_jobs, failed_jobs, created_at, total_cost
   - Pagination via last_key

2. **`get_batch.py`:**
   - Route: `GET /jobs/batches/{batch_id}`
   - Fetch batch from Batches table
   - Fetch all referenced jobs from Jobs table (batch_get_item for efficiency)
   - Return: full batch details + array of job summaries (status, records, cost per job)
   - Verify ownership

3. **`delete_batch.py`:**
   - Route: `DELETE /jobs/batches/{batch_id}`
   - Fetch batch, verify ownership
   - For each job in batch: cancel if RUNNING/QUEUED (reuse delete_job logic), delete if terminal
   - Delete batch record
   - Return: `{ message, jobs_cancelled, jobs_deleted }`

**Verification Checklist:**
- [x] List returns user's batches only
- [x] Get returns batch with job details
- [x] Delete cancels running jobs and removes batch
- [x] Ownership checks on all endpoints
- [x] Pagination works on list

**Testing Instructions:**

Write tests in `tests/unit/test_batch_crud.py`:
```python
# 1. test_list_batches_user_scoped — User A has 2 batches, user B has 1. Assert user A sees only 2.
# 2. test_get_batch_with_jobs — Batch with 3 jobs. Assert job details included.
# 3. test_get_batch_not_owner — Assert 403.
# 4. test_delete_batch_cancels_running — Batch with 1 RUNNING, 1 COMPLETED job. Assert RUNNING cancelled, COMPLETED deleted.
# 5. test_delete_batch_removes_record — Assert batch record deleted from table.
```

**Commit Message Template:**
```
feat(lambdas): add batch list, detail, and delete endpoints

- GET /jobs/batches lists user's batches
- GET /jobs/batches/{id} includes job-level details
- DELETE /jobs/batches/{id} cancels running jobs and cleans up
```

---

## Task 4: Batch Management — Frontend

**Goal:** Build the frontend for batch job creation and monitoring. Add a batch creation flow and a BatchDetail page showing comparative results.

**Files to Modify/Create:**
- `frontend/src/routes/CreateBatch.tsx` — New page component
- `frontend/src/routes/BatchDetail.tsx` — New page component
- `frontend/src/services/api.ts` — New API functions + Zod schemas
- `frontend/src/components/BatchJobTable.tsx` — Comparison table
- `frontend/src/App.tsx` — New routes
- `frontend/src/components/Sidebar.tsx` — Navigation update
- Tests for each new component

**Prerequisites:**
- Tasks 2-3 complete (batch endpoints exist)

**Implementation Steps:**

1. **API service additions:**
   - `createBatch(config): Promise<{ batch_id, job_ids }>`
   - `listBatches(): Promise<Batch[]>`
   - `fetchBatchDetail(batchId): Promise<BatchDetail>`
   - `deleteBatch(batchId): Promise<void>`
   - Zod schemas for Batch and BatchDetail

2. **CreateBatch page:**
   - Step 1: Select template (reuse template selector from CreateJob)
   - Step 2: Upload seed data (or select existing for seed sweep)
   - Step 3: Configure base parameters (budget, records, format)
   - Step 4: Configure sweep:
     - Dropdown: "Vary by Model Tier" / "Vary by Seed Data" / "Vary by Record Count"
     - Dynamic input based on selection:
       - Model tier: checkboxes for tier-1, tier-2, tier-3
       - Seed data: multi-file upload
       - Record count: comma-separated numbers
   - Step 5: Review — show grid of jobs that will be created
   - Create button → calls createBatch API → navigates to BatchDetail

3. **BatchDetail page:**
   - Route: `/jobs/batches/:batchId`
   - Uses `useQuery({ queryKey: ['batch', batchId] })` with polling while any job is RUNNING
   - Layout:
     - Header: batch name, overall status, progress (X of Y complete)
     - BatchJobTable: comparison table with columns per job
     - Columns: Sweep Value (e.g., "Tier-1"), Status, Records, Cost, Time
     - Rows sortable by any column
   - Actions: Cancel batch, Delete batch (with confirmation)

4. **Dashboard integration:**
   - Add "Batches" section or tab to Dashboard page showing recent batches
   - Each batch links to BatchDetail page

5. **Navigation:**
   - Add "Create Batch" option in sidebar (or as sub-option under Jobs)
   - Add routes: `/jobs/batch/new`, `/jobs/batches/:batchId`

**Verification Checklist:**
- [x] Batch creation wizard walks through all 5 steps
- [x] Sweep configuration creates correct number of jobs
- [x] BatchDetail shows comparative table
- [x] Batch status updates via polling
- [x] Cancel/Delete batch works
- [x] Dashboard shows recent batches

**Testing Instructions:**

Create tests for key components:
```typescript
// CreateBatch.test.tsx
// 1. test: renders all wizard steps
// 2. test: model tier sweep shows 3 checkboxes
// 3. test: review step shows correct number of jobs
// 4. test: create calls API with correct config

// BatchDetail.test.tsx
// 5. test: renders batch header with progress
// 6. test: renders comparison table with all jobs
// 7. test: cancel button calls deleteBatch

// BatchJobTable.test.tsx
// 8. test: renders columns for each job
// 9. test: sorts by cost column
```

**Commit Message Template:**
```
feat(frontend): add batch job creation and comparison UI

- CreateBatch wizard with sweep configuration
- BatchDetail page with comparative job table
- Dashboard integration for recent batches
```

---

## Task 5: Seed Data Generation — Backend

**Goal:** Create a Lambda endpoint that generates seed data records from a template's schema requirements using a Bedrock LLM call, then stores them in S3 ready for job creation.

**Files to Modify/Create:**
- `backend/lambdas/seed_data/generate_seed_data.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_generate_seed_data.py` — Unit tests

**Prerequisites:**
- Understanding of `schema_requirements` field (list of dot-notation paths, e.g., `["author.name", "author.biography", "poem.text"]`)
- Understanding of `validate_seed_data()` in `shared/utils.py`
- Understanding of Bedrock model invocation in `backend/ecs_tasks/worker/template_engine.py`

**Implementation Steps:**

1. **`generate_seed_data.py` handler:**
   - Route: `POST /seed-data/generate`
   - Request body:
     ```json
     {
       "template_id": "tmpl-123",
       "count": 10,
       "model_tier": "tier-1",
       "example_data": {
         "author": {"name": "Emily Dickinson", "biography": "American poet..."},
         "poem": {"text": "Because I could not stop for Death..."}
       },
       "instructions": "Generate diverse authors from different eras and cultures"
     }
     ```
   - `count`: 1-100 seed records to generate
   - `model_tier`: which Bedrock model to use (default tier-1 for cost efficiency)
   - `example_data`: optional example record to guide generation style
   - `instructions`: optional free-text guidance for the LLM
   - Logic:
     a. Fetch template from Templates table to get `schema_requirements`
     b. Build a prompt that instructs the LLM to generate `count` JSON records matching the schema
     c. The prompt should include:
        - The schema fields with their nesting structure
        - The example record (if provided) as a reference
        - The instructions (if provided)
        - Explicit instruction to output valid JSON array
     d. Call Bedrock via `ecs_tasks/worker/template_engine.py`'s `_invoke_bedrock()` method (reuse existing model invocation logic — copy or import the function since it lives in the worker package, not in `shared/`)
     e. Parse the LLM output as JSON array
     f. Validate each record against schema_requirements using `validate_seed_data()`
     g. Filter out invalid records (log warnings)
     h. Upload valid records to S3 as JSONL: `seed-data/{user_id}/generated-{timestamp}.jsonl`
     i. Return: `{ s3_key, records_generated, records_invalid, total_cost }`
   - Lambda timeout: 60 seconds (LLM call can be slow for 100 records)
   - Lambda memory: 512 MB

2. **Prompt design:**
   ```
   Generate exactly {count} unique JSON objects. Each object must have the following structure:

   Required fields:
   - author.name (string): Full name of the author
   - author.biography (string): 2-3 sentence biography
   - poem.text (string): A short poem or excerpt

   {example_section}
   {instructions_section}

   Output ONLY a JSON array with no other text. Example format:
   [
     {"author": {"name": "...", "biography": "..."}, "poem": {"text": "..."}},
     ...
   ]
   ```

3. **JSON extraction:**
   - LLMs sometimes wrap JSON in markdown code blocks. Strip ``` markers.
   - Try `json.loads()` on the full output first.
   - If that fails, try extracting content between `[` and `]`.
   - If that fails, return error with raw output for debugging.

**Verification Checklist:**
- [x] Generates correct number of seed records
- [x] Records match template schema requirements
- [x] Invalid records filtered out (not uploaded)
- [x] S3 path follows pattern `seed-data/{user_id}/generated-{timestamp}.jsonl`
- [x] Handles LLM markdown wrapper around JSON
- [x] Returns cost estimate for the generation
- [x] Works with example_data and instructions
- [x] Works without example_data (schema-only)

**Testing Instructions:**

Write tests in `tests/unit/test_generate_seed_data.py`:
```python
# 1. test_generate_success — Mock Bedrock returning valid JSON array. Assert S3 upload called, correct count returned.
# 2. test_generate_filters_invalid — Mock Bedrock returning 10 records, 2 invalid. Assert records_generated=8, records_invalid=2.
# 3. test_generate_strips_markdown — Mock Bedrock returning ```json\n[...]\n```. Assert parses correctly.
# 4. test_generate_with_example — Assert prompt includes example data.
# 5. test_generate_with_instructions — Assert prompt includes user instructions.
# 6. test_generate_template_not_found — Assert 404.
# 7. test_generate_invalid_json_from_llm — Mock Bedrock returning non-JSON. Assert 500 with helpful error.
# 8. test_generate_max_count — Request count=101. Assert 400.
```

**Commit Message Template:**
```
feat(lambdas): add seed data generation from template schema

- POST /seed-data/generate creates seed records via Bedrock
- Validates generated records against template schema
- Filters invalid records, uploads valid ones to S3
- Supports example data and custom instructions
```

---

## Task 6: Seed Data Generation — Frontend

**Goal:** Add a "Generate Seed Data" option to the job creation flow, allowing users to auto-generate seed data instead of uploading a file.

**Files to Modify/Create:**
- `frontend/src/services/api.ts` — New API function
- `frontend/src/routes/CreateJob.tsx` — Add generation option to step 2
- `frontend/src/components/SeedDataGenerator.tsx` — New component
- `frontend/src/components/SeedDataGenerator.test.tsx` — Tests
- `frontend/src/routes/CreateJob.test.tsx` — Updated tests

**Prerequisites:**
- Task 5 complete (generation endpoint exists)

**Implementation Steps:**

1. **API service addition:**
   - `generateSeedData(params: { template_id, count, model_tier?, example_data?, instructions? }): Promise<{ s3_key, records_generated, records_invalid, total_cost }>`

2. **SeedDataGenerator component:**
   - Props: `{ templateId: string, onGenerated: (s3Key: string, count: number) => void }`
   - Layout:
     - Record count input (1-100, default 10)
     - Model tier selector (Tier-1 recommended for cost, Tier-3 for quality)
     - Optional: example data textarea (JSON format)
     - Optional: instructions textarea
     - "Generate" button
     - Progress/loading state during generation
     - Success state: "Generated X records (Y invalid filtered). Cost: $Z.ZZ"
     - Calls `onGenerated(s3Key, count)` on success to advance the wizard

3. **CreateJob step 2 update:**
   - Two options: "Upload File" (existing) or "Generate from Schema"
   - Radio buttons or tabs to switch between modes
   - "Generate from Schema" shows SeedDataGenerator component
   - Template ID from step 1 is passed to the generator
   - When generation completes, `seed_data_path` is set to the returned `s3_key`

**Verification Checklist:**
- [x] Two options available in seed data step
- [x] Generate mode shows count, model tier, and optional fields
- [x] Generation progress shown during API call
- [x] Success shows record count and cost
- [x] Generated s3_key used as seed_data_path for job creation
- [x] Can switch between upload and generate modes

**Testing Instructions:**

Create `frontend/src/components/SeedDataGenerator.test.tsx`:
```typescript
// 1. test: renders count input and generate button
// 2. test: calls API with correct parameters on generate
// 3. test: shows loading state during generation
// 4. test: shows success with record count on completion
// 5. test: calls onGenerated callback with s3_key
// 6. test: shows error toast on failure
```

Update `frontend/src/routes/CreateJob.test.tsx`:
```typescript
// 7. test: step 2 shows upload and generate options
// 8. test: switching to generate mode shows SeedDataGenerator
```

**Commit Message Template:**
```
feat(frontend): add seed data generation to job creation wizard

- SeedDataGenerator component with count, model tier, instructions
- Toggle between upload and generate in job creation step 2
- Automatic s3_key handoff to job creation
```

---

## Task 7: Infrastructure Updates for Phase 4

**Goal:** Add all new resources to the SAM template.

**Files to Modify/Create:**
- `backend/template.yaml` — New tables, functions, routes

**Prerequisites:**
- All handler code from Tasks 1-6 exists

**Implementation Steps:**

1. **Batches table** (from Task 1)

2. **New Lambda functions:**
   - `CreateBatchFunction`: `POST /jobs/batch`, 512MB, 60s timeout, DynamoDB write on Jobs + Batches, SFN StartExecution
   - `ListBatchesFunction`: `GET /jobs/batches`, 256MB, 15s, DynamoDB read on Batches (GSI)
   - `GetBatchFunction`: `GET /jobs/batches/{batch_id}`, 256MB, 15s, DynamoDB read on Batches + Jobs
   - `DeleteBatchFunction`: `DELETE /jobs/batches/{batch_id}`, 256MB, 30s, DynamoDB read/write/delete on Batches + Jobs, SFN StopExecution
   - `GenerateSeedDataFunction`: `POST /seed-data/generate`, 512MB, 60s, DynamoDB read on Templates, S3 write, Bedrock InvokeModel

3. **Add `BATCHES_TABLE_NAME` to Globals environment variables.**

4. **Bedrock permissions** for GenerateSeedDataFunction:
   - `bedrock:InvokeModel` on `*` (same as existing worker permissions)

**Verification Checklist:**
- [ ] `cfn-lint backend/template.yaml` passes
- [ ] All functions have correct routes, timeouts, and memory
- [ ] Batches table has correct schema and GSI
- [ ] Bedrock permissions granted to generate function

**Commit Message Template:**
```
feat(infra): add batch jobs and seed generation SAM resources

- Batches DynamoDB table with user-id-index GSI
- Batch CRUD Lambda functions (create, list, get, delete)
- Seed data generation Lambda with Bedrock permissions
```

---

## Task 8: Integration Tests for Phase 4

**Goal:** Integration tests for batch creation and seed data generation.

**Files to Modify/Create:**
- `tests/integration/test_batch_jobs.py` — Integration tests
- `tests/integration/test_seed_generation.py` — Integration tests

**Prerequisites:**
- Tasks 1-6 complete

**Implementation Steps:**

1. **Batch jobs integration test:**
   - Create Jobs, Batches, and Templates tables with moto
   - Insert a template
   - Invoke create_batch handler with model_tier sweep of 3 values
   - Assert 3 jobs created in Jobs table
   - Assert batch record in Batches table with 3 job_ids
   - Invoke get_batch handler — assert returns batch with job details
   - Invoke list_batches — assert batch appears in user's list
   - Mock SFN client for start_execution calls

2. **Seed data generation integration test:**
   - Create Templates table with moto, insert template with schema_requirements
   - Mock Bedrock client to return valid JSON array of records
   - Create S3 bucket with moto
   - Invoke generate_seed_data handler
   - Assert JSONL file uploaded to correct S3 path
   - Read uploaded file and verify record structure matches schema

**Verification Checklist:**
- [ ] Batch creates correct number of jobs
- [ ] Batch record links to all job IDs
- [ ] Generated seed data uploaded to S3 in JSONL format
- [ ] Seed data records match template schema

**Commit Message Template:**
```
test(integration): add batch jobs and seed generation integration tests

- Batch: create, get, list with moto DynamoDB
- Seed generation: Bedrock mock, S3 upload verification, schema validation
```

---

## Phase Verification

After completing all tasks in Phase 4:

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
- Batch sweep is single-dimension only (no combinatorial sweeps like model x seed_data)
- MAX_BATCH_SIZE of 20 caps the sweep size
- Seed data generation quality depends on the LLM model used. Tier-1 (Llama 8B) may produce lower quality or less diverse records than Tier-3 (Claude Sonnet).
- LLM JSON output parsing is best-effort. Some records may be filtered out as invalid.
- No deduplication of generated seed data records.
- Batch status tracking requires polling the batch endpoint (no SSE for batches in MVP).

### What Phase 5 Builds On
- Phase 5's quality scoring will benefit from batch jobs (score and compare across model tiers)
- Phase 5's quality metrics can be displayed in the BatchDetail comparison table
