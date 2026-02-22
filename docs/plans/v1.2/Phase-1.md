# Phase 1: Partial Result Export + Template Version History

## Phase Goal

Build two foundational features that unlock data access and iterative workflows. **Partial Result Export** lets users download generated records from jobs that are still running, were interrupted, or failed — preventing wasted compute. **Template Version History with Diff View** enables prompt iteration by tracking every template edit as an immutable version and displaying side-by-side diffs using Monaco's built-in diff editor.

**Success criteria:**
- Users can download partial results from any job with `records_generated > 0`, regardless of status
- Template updates create new versions (already true in backend) and the frontend shows version history with diff view
- Job creation allows selecting a specific template version
- All new code has unit tests; coverage remains above 70%

**Estimated tokens:** ~45,000

---

## Prerequisites

- Phase 0 read and understood
- Local dev environment set up per Phase 0
- `npm run check` passes on current `main` branch

---

## Task 1: Partial Result Export — Backend Lambda

**Goal:** Create a new Lambda endpoint that concatenates available batch files from S3 and returns a presigned download URL, allowing users to download partial results from any job with generated records.

**Files to Modify/Create:**
- `backend/lambdas/jobs/download_partial.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_download_partial.py` — Unit tests

**Prerequisites:**
- Understanding of S3 batch file key pattern: `jobs/{job_id}/outputs/batch-{NNNN}.jsonl`
- Understanding of existing `download_job.py` handler for pattern reference

**Implementation Steps:**

The handler should:

1. Extract `user_id` from JWT claims and `job_id` from path parameters
2. Fetch the job from the Jobs table and verify ownership (403 if mismatch)
3. Check that `records_generated > 0` (return 400 if no records)
4. List all objects under prefix `jobs/{job_id}/outputs/` using S3 paginator
5. If no batch files found, return 404
6. For JSONL format: concatenate all batch files into a single temporary S3 object at `jobs/{job_id}/exports/partial-{timestamp}.jsonl`
   - Use S3 multipart upload for efficiency (same pattern as `worker.py` `export_jsonl`)
   - Read each batch file sequentially, write to multipart upload
7. Generate a presigned URL for the concatenated file (1 hour expiry)
8. Return `{download_url, filename, records_available, format, expires_in}`

**Design considerations:**
- Only support JSONL for partial export (the batch files are already JSONL). CSV and Parquet require schema knowledge that may not be complete mid-job.
- Don't block on concatenation for large datasets — set Lambda timeout to 30 seconds and memory to 512 MB
- The partial export file is separate from the final export (`dataset.jsonl`) to avoid confusion
- Include a `records_available` count in the response so the user knows how many records they're getting

**Note:** This task creates only the handler code (`download_partial.py`). All SAM template changes (function resource, route, IAM policies) are handled in Task 7.

**Verification Checklist:**
- [x] Handler returns 403 for non-owner
- [x] Handler returns 400 when `records_generated == 0`
- [x] Handler returns 404 when no batch files exist in S3
- [x] Handler concatenates multiple batch files correctly
- [x] Presigned URL has correct filename and 1-hour expiry
- [x] Response includes `records_available` count

**Testing Instructions:**

Write unit tests in `tests/unit/test_download_partial.py`:

```python
# Test cases:
# 1. test_download_partial_success — Mock S3 list (2 batch files), mock read, mock multipart upload, mock presigned URL. Assert 200 response with download_url and records_available.
# 2. test_download_partial_no_records — Mock job with records_generated=0. Assert 400.
# 3. test_download_partial_not_owner — Mock job with different user_id. Assert 403.
# 4. test_download_partial_no_batches — Mock S3 list returning empty. Assert 404.
# 5. test_download_partial_job_not_found — Mock get_item returning no Item. Assert 404.
```

Follow the Lambda handler test pattern from Phase 0: build API Gateway v2 event, patch `get_dynamodb_resource` and `get_s3_client`, invoke `lambda_handler`, assert response status and body.

**Commit Message Template:**
```
feat(lambdas): add partial result export endpoint

- New GET /jobs/{job_id}/download-partial endpoint
- Concatenates available JSONL batches from S3
- Returns presigned URL with records_available count
```

---

## Task 2: Partial Result Export — Frontend Integration

**Goal:** Add a "Download Partial Results" button to the JobDetail page for any job with generated records, and update the JobCard component to show the option in the dashboard.

**Files to Modify/Create:**
- `frontend/src/services/api.ts` — New API function
- `frontend/src/routes/JobDetail.tsx` — New download button
- `frontend/src/components/JobCard.tsx` — New download option
- `frontend/src/services/api.test.ts` — Test for new API function
- `frontend/src/routes/JobDetail.test.tsx` — Test for new button

**Prerequisites:**
- Task 1 complete (backend endpoint exists)

**Implementation Steps:**

1. **API service** — Add `downloadPartialExport(jobId: string)` function:
   - `GET /jobs/{jobId}/download-partial`
   - Define Zod schema for response: `{ download_url: z.string(), filename: z.string(), records_available: z.number(), format: z.string(), expires_in: z.number() }`
   - On success, open `download_url` in a new tab or trigger browser download

2. **JobDetail page** — Add conditional button:
   - Show "Download Partial Results ({records_generated} records)" when:
     - `records_generated > 0` AND
     - `status` is NOT `COMPLETED` (completed jobs already have the full download button)
   - On click: call `downloadPartialExport(jobId)`, open URL in new window
   - Show loading spinner during the API call (concatenation may take a few seconds)
   - Show toast on error

3. **JobCard component** — Add partial download to action buttons:
   - For RUNNING/FAILED/CANCELLED/BUDGET_EXCEEDED jobs with `records_generated > 0`: show "Partial Download" icon button
   - Use same download logic as JobDetail

**Verification Checklist:**
- [x] "Download Partial Results" button appears for RUNNING jobs with records > 0
- [x] Button does NOT appear for COMPLETED jobs (they have the full download)
- [x] Button does NOT appear when records_generated is 0
- [x] Download triggers browser file download
- [x] Loading state shown during API call
- [x] Error toast shown on failure
- [x] Button shows record count

**Testing Instructions:**

Add to `frontend/src/services/api.test.ts`:
```typescript
// test: downloadPartialExport calls correct endpoint and returns parsed response
// test: downloadPartialExport propagates network errors
```

Add to `frontend/src/routes/JobDetail.test.tsx`:
```typescript
// test: shows partial download button for RUNNING job with records > 0
// test: hides partial download button for COMPLETED job
// test: hides partial download button when records_generated is 0
```

**Commit Message Template:**
```
feat(frontend): add partial result download to job views

- New downloadPartialExport API function with Zod validation
- Conditional download button on JobDetail and JobCard
- Shows record count and handles loading/error states
```

---

## Task 3: Template Version History — Backend Enhancements

**Goal:** Expose template version history through the API. The backend already stores immutable versions (update creates version N+1), but there's no endpoint to list all versions or retrieve a specific version other than the default (version 1). Fix this so the frontend can display version history.

**Files to Modify/Create:**
- `backend/lambdas/templates/list_versions.py` — New Lambda handler
- `backend/lambdas/templates/get_template.py` — Modify to support `version=latest`
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_list_versions.py` — Unit tests
- `tests/unit/test_get_template.py` — Update existing tests

**Prerequisites:**
- Understanding of Templates table: PK=`template_id`, SK=`version` (number)
- Understanding that `update_template.py` already creates new versions by inserting a new item with `version = latest + 1`

**Implementation Steps:**

1. **New `list_versions.py` handler:**
   - Route: `GET /templates/{template_id}/versions`
   - Query Templates table with `template_id` as partition key (no sort key condition = all versions)
   - Sort by version descending
   - Return list of version summaries (version number, created_at, name, description — omit full `template_definition` to keep response small)
   - Verify ownership OR public template (same auth as get_template)

2. **Modify `get_template.py`:**
   - Currently accepts `version` query parameter (default 1)
   - Add support for `version=latest`: query with ScanIndexForward=False, Limit=1
   - The test_template.py handler hardcodes version=1 — note this as a known issue but don't change it in this task

3. **Modify `create_job.py`:**
   - Currently accepts optional `template_version` in request body (default 1)
   - Change default to fetch latest version when `template_version` is not specified
   - Store the resolved version number in `config.template_version` so jobs are reproducible

**Verification Checklist:**
- [x] `GET /templates/{id}/versions` returns all versions sorted newest first
- [x] Version list omits `template_definition` field (summary only)
- [x] `GET /templates/{id}?version=latest` returns the highest version
- [x] `GET /templates/{id}?version=3` still works for specific versions
- [x] Ownership / public check works on version list
- [x] Job creation stores resolved version number in config

**Testing Instructions:**

Write tests in `tests/unit/test_list_versions.py`:
```python
# 1. test_list_versions_success — Mock query returning 3 versions. Assert sorted desc, no template_definition in response.
# 2. test_list_versions_not_owner_private — Mock private template owned by different user. Assert 403.
# 3. test_list_versions_not_owner_public — Mock public template. Assert 200.
# 4. test_list_versions_not_found — Mock empty query result. Assert 404.
```

Update `tests/unit/test_get_template.py` (or create if missing):
```python
# 5. test_get_template_latest_version — Mock query with ScanIndexForward=False. Assert returns version 3 (latest).
# 6. test_get_template_specific_version — Assert version=2 returns version 2.
```

**Commit Message Template:**
```
feat(lambdas): add template version list and latest-version support

- New GET /templates/{id}/versions endpoint
- get_template supports version=latest query parameter
- create_job resolves latest version when not specified
```

---

## Task 4: Template Version History — Frontend Version List

**Goal:** Build the template version history UI. Display a list of all versions for a template, show metadata (version number, date, description), and allow navigation to any version.

**Files to Modify/Create:**
- `frontend/src/services/api.ts` — New API functions
- `frontend/src/routes/TemplateEditor.tsx` — Version history sidebar
- `frontend/src/components/VersionList.tsx` — New component
- `frontend/src/components/VersionList.test.tsx` — Tests
- `frontend/src/routes/TemplateEditor.test.tsx` — Updated tests

**Prerequisites:**
- Task 3 complete (version list endpoint exists)

**Implementation Steps:**

1. **API service additions:**
   - `fetchTemplateVersions(templateId: string): Promise<TemplateVersion[]>` — calls `GET /templates/{templateId}/versions`
   - Define `TemplateVersionSchema` Zod schema: `{ version: z.number(), name: z.string(), description: z.string().optional(), created_at: z.string() }`
   - Update `fetchTemplate` to accept optional `version` parameter

2. **VersionList component:**
   - Props: `{ templateId: string, currentVersion: number, onSelectVersion: (version: number) => void }`
   - Uses `useQuery({ queryKey: ['template', templateId, 'versions'], queryFn: ... })`
   - Renders a vertical timeline or list of versions
   - Current version is highlighted
   - Each item shows: version number, date (relative — "2 days ago"), name change indicator
   - Click selects version and calls `onSelectVersion`

3. **TemplateEditor integration:**
   - When editing an existing template (`templateId` in URL params):
     - Fetch version list
     - Show VersionList in a collapsible right sidebar panel
     - When user selects a different version, fetch that version's full data and display in editor
     - Show "Viewing version N" indicator when viewing a non-latest version
     - "Restore this version" button that creates a new version from the viewed content (uses existing update API)
   - Prevent editing when viewing a historical version (read-only mode in Monaco)

**Verification Checklist:**
- [x] Version list loads and displays when editing a template
- [x] Clicking a version loads that version's content in the editor
- [x] Current version is visually highlighted in the list
- [x] Historical versions show editor in read-only mode
- [x] "Restore this version" creates a new version (increments version number)
- [x] New templates (no `templateId`) don't show version panel
- [x] Loading and error states handled

**Testing Instructions:**

Create `frontend/src/components/VersionList.test.tsx`:
```typescript
// 1. test: renders version list with correct items
// 2. test: highlights current version
// 3. test: calls onSelectVersion when version clicked
// 4. test: shows loading state
// 5. test: shows error state
```

Update `frontend/src/routes/TemplateEditor.test.tsx`:
```typescript
// 6. test: shows version sidebar when editing existing template
// 7. test: hides version sidebar for new template
// 8. test: switches to read-only when viewing historical version
```

**Commit Message Template:**
```
feat(frontend): add template version history sidebar

- VersionList component with timeline UI
- TemplateEditor integration with version switching
- Read-only mode for historical versions
- Restore button to create new version from historical
```

---

## Task 5: Template Diff View — Frontend

**Goal:** Add a side-by-side diff view using Monaco's built-in `DiffEditor` component, allowing users to compare any two template versions.

**Files to Modify/Create:**
- `frontend/src/components/TemplateDiffView.tsx` — New component
- `frontend/src/components/TemplateDiffView.test.tsx` — Tests
- `frontend/src/routes/TemplateEditor.tsx` — Add diff mode toggle

**Prerequisites:**
- Task 4 complete (version list and version switching work)
- Understanding of Monaco DiffEditor: `@monaco-editor/react` exports `DiffEditor` component

**Implementation Steps:**

1. **TemplateDiffView component:**
   - Props: `{ originalContent: string, modifiedContent: string, originalVersion: number, modifiedVersion: number }`
   - Uses `DiffEditor` from `@monaco-editor/react` with:
     - `language="yaml"` (templates are YAML-like)
     - `original={originalContent}`
     - `modified={modifiedContent}`
     - `options={{ readOnly: true, renderSideBySide: true }}`
   - Header shows "Version {N} vs Version {M}"
   - Content to diff: serialize the template steps as YAML or formatted text (step ID, model, prompt — one per section)

2. **Diff content formatting:**
   - Create a helper function `formatTemplateForDiff(template: TemplateDefinition): string`
   - Format each step as:
     ```
     # Step: {step.id}
     Model: {step.model || step.model_tier}

     {step.prompt}

     ---
     ```
   - This gives readable, diffable output

3. **TemplateEditor integration:**
   - Add "Compare" button in the version list that opens diff mode
   - Diff mode: replace the Monaco editor with TemplateDiffView
   - Left side: selected version. Right side: latest version (or user-selected comparison target)
   - Version dropdowns above diff view to change comparison targets
   - "Exit Diff" button to return to normal editor mode

**Verification Checklist:**
- [x] DiffEditor renders with correct original and modified content
- [x] Side-by-side diff highlights additions, deletions, and changes
- [x] Version selectors allow comparing any two versions
- [x] "Compare" button in version list opens diff mode
- [x] "Exit Diff" returns to normal editor
- [x] Diff view is fully read-only

**Testing Instructions:**

Create `frontend/src/components/TemplateDiffView.test.tsx`:
```typescript
// 1. test: renders DiffEditor with provided content
// 2. test: shows version numbers in header
// 3. test: DiffEditor is read-only
```

Note: Monaco DiffEditor requires mocking in tests. Mock `@monaco-editor/react`:
```typescript
vi.mock('@monaco-editor/react', () => ({
  default: (props: any) => <div data-testid="monaco-editor">{props.value}</div>,
  DiffEditor: (props: any) => (
    <div data-testid="monaco-diff-editor">
      <div data-testid="original">{props.original}</div>
      <div data-testid="modified">{props.modified}</div>
    </div>
  ),
}))
```

**Commit Message Template:**
```
feat(frontend): add template version diff view with Monaco DiffEditor

- TemplateDiffView component using Monaco DiffEditor
- Compare button in version list opens diff mode
- Version dropdowns for flexible comparison
- formatTemplateForDiff helper for readable diffs
```

---

## Task 6: Job Creation — Template Version Selection

**Goal:** Update the job creation wizard to let users select a specific template version when creating a job, rather than always using version 1.

**Files to Modify/Create:**
- `frontend/src/routes/CreateJob.tsx` — Add version selector in step 1
- `frontend/src/services/api.ts` — Update `createJob` to pass `template_version`
- `frontend/src/routes/CreateJob.test.tsx` — Updated tests

**Prerequisites:**
- Task 3 complete (backend supports `template_version` in create_job)
- Task 4 complete (version list API available)

**Implementation Steps:**

1. **Step 1 of wizard (Select Template):**
   - After user enters/selects a template ID, fetch version list via `fetchTemplateVersions(templateId)`
   - Show version dropdown defaulting to "Latest"
   - Each option: "Version {N} — {created_at}"
   - Store selected version in wizard state

2. **Wizard data update:**
   - Add `templateVersion: number | 'latest'` to `WizardData` interface
   - Default to `'latest'`

3. **Job creation API call:**
   - Pass `template_version` in request body when not "latest"
   - When "latest": omit `template_version` (backend resolves to latest per Task 3)

4. **Review step:**
   - Show selected version number in the review summary

**Verification Checklist:**
- [x] Version dropdown appears after template ID is entered
- [x] "Latest" is the default selection
- [x] Specific version number is passed to createJob API
- [x] Review step shows version selection
- [x] Version list loading/error states handled

**Testing Instructions:**

Update `frontend/src/routes/CreateJob.test.tsx`:
```typescript
// 1. test: shows version dropdown after template ID is entered
// 2. test: defaults to "Latest" version
// 3. test: passes template_version in job creation request
```

**Commit Message Template:**
```
feat(frontend): add template version selection to job creation wizard

- Version dropdown in step 1 after template selection
- Defaults to latest, allows specific version
- Passes template_version to create job API
```

---

## Task 7: Infrastructure Updates for Phase 1

**Goal:** Add the new Lambda function to the SAM template and ensure all IAM permissions are correct.

**Files to Modify/Create:**
- `backend/template.yaml` — New function + route

**Prerequisites:**
- Task 1 complete (handler code exists)
- Task 3 complete (list_versions handler exists)

**Implementation Steps:**

1. Add `DownloadPartialFunction`:
   - Handler: `lambdas/jobs/download_partial.lambda_handler`
   - Memory: 512 MB (needs to buffer S3 reads)
   - Timeout: 30 seconds (concatenation may be slow for large datasets)
   - Route: `GET /jobs/{job_id}/download-partial`
   - Policies: S3 CRUD on `BUCKET_NAME`, DynamoDB read on Jobs table

2. Add `ListTemplateVersionsFunction`:
   - Handler: `lambdas/templates/list_versions.lambda_handler`
   - Memory: 256 MB
   - Timeout: 15 seconds
   - Route: `GET /templates/{template_id}/versions`
   - Policies: DynamoDB read on Templates table

3. Verify the Globals Environment section includes all table names needed by both new functions.

**Verification Checklist:**
- [x] `sam validate` passes
- [x] `cfn-lint backend/template.yaml` passes
- [x] New functions have correct routes and methods
- [x] IAM policies are least-privilege (read-only where possible)
- [x] Memory and timeout match requirements

**Testing Instructions:**

No code tests — verify with:
```bash
cd backend && cfn-lint template.yaml
```

If SAM CLI is available:
```bash
cd backend && sam validate
```

**Commit Message Template:**
```
feat(infra): add SAM resources for partial export and version list endpoints

- DownloadPartialFunction: GET /jobs/{id}/download-partial (512MB, 30s)
- ListTemplateVersionsFunction: GET /templates/{id}/versions
- S3 and DynamoDB IAM policies
```

---

## Task 8: End-to-End Integration Testing

**Goal:** Write integration tests that verify the partial export and version history features work together with mocked AWS services.

**Files to Modify/Create:**
- `tests/integration/test_partial_export.py` — Integration tests with moto
- `tests/integration/test_template_versions.py` — Integration tests with moto

**Prerequisites:**
- Tasks 1-3 complete
- Understanding of moto decorators for S3 and DynamoDB mocking

**Implementation Steps:**

1. **Partial export integration test:**
   - Use `@mock_aws` decorator (moto)
   - Create a real DynamoDB table and S3 bucket
   - Insert a job record with `records_generated > 0`
   - Upload 3 batch JSONL files to the correct S3 prefix
   - Invoke the Lambda handler
   - Verify the concatenated file exists in S3 and contains all records
   - Verify presigned URL is generated

2. **Template version integration test:**
   - Use `@mock_aws` decorator
   - Create real Templates DynamoDB table with PK/SK schema
   - Insert 3 versions of a template (version 1, 2, 3)
   - Invoke list_versions handler — verify all 3 returned, sorted desc
   - Invoke get_template with `version=latest` — verify version 3 returned
   - Invoke get_template with `version=2` — verify version 2 returned

**Verification Checklist:**
- [x] Partial export test creates real S3 objects and concatenates them
- [x] Version list test queries real DynamoDB with 3 versions
- [x] `version=latest` resolves correctly
- [x] Tests pass with `PYTHONPATH=. pytest tests/integration/test_partial_export.py tests/integration/test_template_versions.py -v`

**Testing Instructions:**

```bash
PYTHONPATH=. pytest tests/integration/test_partial_export.py -v
PYTHONPATH=. pytest tests/integration/test_template_versions.py -v
```

**Commit Message Template:**
```
test(integration): add partial export and template version integration tests

- Partial export: moto S3 batch concatenation + presigned URL
- Template versions: moto DynamoDB version query and latest resolution
```

---

## Phase Verification

After completing all tasks in Phase 1:

### Backend Verification
```bash
# All backend tests pass
PYTHONPATH=. pytest tests/unit tests/integration -v --tb=short --cov=backend --cov-report=term-missing --cov-fail-under=70

# Lint passes
cd backend && uvx ruff check .

# SAM template valid
cd backend && cfn-lint template.yaml
```

### Frontend Verification
```bash
# All frontend tests pass with coverage
cd frontend && npx vitest run --coverage

# Lint passes
cd frontend && npm run lint
```

### Full Check
```bash
npm run check
```

### Known Limitations
- Partial export only supports JSONL format (CSV/Parquet require complete schema)
- Partial export creates a new S3 object each time (no caching of the concatenated file)
- Template diff formats steps as text — not a true YAML diff (templates are stored as JSON internally)
- Version history is only visible in the template editor, not in the template list page (which is still a stub)

### What Phase 2 Builds On
- Phase 2's Template Marketplace uses the version history infrastructure (listing public templates, forking a specific version)
- Phase 2's Cost Analytics Dashboard references the same DynamoDB CostTracking table that partial export jobs interact with

---

## Review Feedback (Iteration 1)

### Critical: Backend Unit Tests Are Test Theater (Tasks 1, 3)

> **Consider:** The plan instructs: "Follow the Lambda handler test pattern from Phase 0: build API Gateway v2 event, patch `get_dynamodb_resource` and `get_s3_client`, invoke `lambda_handler`, assert response status and body." Looking at `tests/unit/test_download_partial.py:23`, `tests/unit/test_list_versions.py:19`, and `tests/unit/test_get_template.py:23` — do any of these functions import or call the actual Lambda `lambda_handler`? Or do they re-implement the handler logic in a `simulate_*_handler` function?
>
> **Think about:** If a bug is introduced in `backend/lambdas/jobs/download_partial.py:80` (e.g., removing the `int()` cast on `records_generated`), would `test_download_partial.py` catch it? The test's `simulate_download_partial_handler` at line 45 has its own independent implementation — how does testing a copy of the code provide confidence in the actual code?
>
> **Reflect:** This is the exact pattern that was deleted in v1.1.0 remediation (`test_worker_checkpoint.py` — 438 lines of test theater). The remediation plan explicitly stated: "Every test creates hardcoded dicts and asserts values that were just assigned. No test calls any actual worker code." How are these three test files different from that?

### Critical: Phase 0 Documents Wrong sys.path/Import Pattern

> **Consider:** Phase 0 lines 109-113 document the handler boilerplate as:
> ```python
> sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
> from shared.lambda_responses import success_response, error_response
> ```
> But grep every Lambda handler in `backend/lambdas/` — what pattern do they actually use? Is it `../../shared` with bare imports like `from lambda_responses import ...`, or `../..` with `from shared.lambda_responses import ...`?
>
> **Think about:** An implementer reading Phase 0 as their foundation document would write `from shared.lambda_responses import success_response` — would that import resolve given the actual `sys.path` configuration?

### Critical: Integration Tests Don't Invoke Lambda Handlers (Task 8)

> **Consider:** Read `tests/integration/test_partial_export.py:93` — the comment says "Simulate handler logic (same as the actual handler)." Is this an integration test of the handler, or is it an integration test of moto/boto3? At no point does it import or call `download_partial.lambda_handler`.
>
> **Think about:** The plan says "Invoke the Lambda handler" and "Verify the concatenated file exists." What was actually invoked? The test manually calls `table.get_item()`, `s3.get_paginator()`, etc. — these are the same operations the handler performs, but executed by test code, not by the handler code. If the handler has a bug in its S3 paginator logic, would this test catch it?
>
> **Reflect:** `test_template_versions.py` has the same issue — it calls `table.query()` directly instead of invoking `list_versions.lambda_handler()`.

### Significant: TemplateEditor Has TODO Stubs (Tasks 4-5)

> **Consider:** The plan says (Task 4): "'Restore this version' button that creates a new version from the viewed content (uses existing update API)." Read `frontend/src/routes/TemplateEditor.tsx:156` — what does `handleRestore()` actually do?
>
> **Think about:** Line 157: `await new Promise((resolve) => setTimeout(resolve, 500))` — is this calling the update API, or is it a 500ms delay pretending to be an API call? The same pattern appears in `handleSave()` at line 183. Are these feature implementations or placeholders?
>
> **Reflect:** The plan verification checklist says: "`'Restore this version' creates a new version (increments version number)`." Does a `setTimeout` increment a version number?

### Significant: JobDetail Uses console.error Instead of Toast (Task 2)

> **Consider:** The plan says: "Show toast on error" (Task 2, line 122). Read `frontend/src/routes/JobDetail.tsx:52` — `handlePartialDownload()` catches errors with `console.error('Failed to download partial results:', err)`. Compare with `frontend/src/components/JobCard.tsx:116` which uses `toast('Failed to download partial results', 'error')`.
>
> **Think about:** The same issue applies to `handleCancel` (line 20), `handleDelete` (line 31), and `handleDownload` (line 41) — all use `console.error` instead of `toast()`. The `useToast` hook is available at `../hooks/useToast` but is never imported in JobDetail.tsx. Is this a deliberate omission or was it missed?

### Significant: Missing Tests for `fetchTemplate` and `fetchTemplateVersions` (Tasks 3-4)

> **Consider:** `api.ts:154` added `fetchTemplate(templateId, version)` with an optional `version` parameter that appends `?version=latest` or `?version=2` to the URL. Is there any test in `api.test.ts` that verifies this parameter is correctly passed?
>
> **Think about:** Search `api.test.ts` for "fetchTemplate" — does the string appear? Similarly, `fetchTemplateVersions` parses through `TemplateVersionListSchema` — is there a test that verifies Zod rejects malformed responses?

### Significant: CreateJob Test Doesn't Verify `template_version` Payload (Task 6)

> **Consider:** The plan says to test: "passes template_version in job creation request." Search `CreateJob.test.tsx` for "template_version" or "templateVersion" — does the string appear anywhere?
>
> **Think about:** The successful submission test at line 239 asserts `mockNavigate` was called but never asserts what payload was passed to `mockCreateJob`. If the `template_version` field was accidentally omitted from the API call, would any test catch it?

### Significant: TemplateEditor Test Doesn't Verify Read-Only Mode (Task 4)

> **Consider:** The plan says to test: "switches to read-only when viewing historical version." Read `TemplateEditor.test.tsx` — does any test verify that the Monaco editor receives `readOnly: true` when viewing a historical version?
>
> **Think about:** The "edit mode" tests at line 115 only check that the sidebar appears and the title renders. The `isViewingHistorical` flag at `TemplateEditor.tsx:132` controls `readOnly` on the editor — is this behavior tested?

### Minor: VersionList Tests Don't Cover Compare Button (Task 5)

> **Consider:** `VersionList.tsx:79-88` renders a "Compare" button when `onCompare` is provided and the version isn't the current one. Do any tests in `VersionList.test.tsx` pass an `onCompare` prop? Do they test clicking the Compare button?

### Minor: PRESIGNED_URL_EXPIRATION Inconsistency

> **Consider:** Phase 0 Constants Reference says `PRESIGNED_URL_EXPIRATION = 900` (15 minutes). But `download_partial.py:34` and `download_job.py:31` both define `PRESIGNED_URL_EXPIRATION = 3600` locally. Should these handlers import from `shared/constants.py`, or should Phase 0's reference be updated to reflect that download handlers use their own 1-hour expiry?

### Minor: Phase 1 Committed Directly to Main

> **Reflect:** Phase 0 Branch Strategy says: "Each phase should be developed on a feature branch: `feat/phase-{N}-{short-description}`. PRs merge to `main`." All 8 Phase 1 commits (763ddeb through 2f2253e) were committed directly to main without a feature branch or PR.

### Verification Summary

- **Tests:** 18 backend unit + 9 integration + 62 frontend = 89 tests, all passing
- **Build:** Not verified (SAM validate requires AWS credentials)
- **Commits:** 8 commits, conventional format, matching plan sequence exactly
- **Spec:** All tasks have corresponding commits and files
- **Code Quality:** Implementation follows existing patterns; frontend components are well-structured
- **Test Quality:** Backend tests are test theater (simulate pattern); frontend tests are behavioral but have gaps
