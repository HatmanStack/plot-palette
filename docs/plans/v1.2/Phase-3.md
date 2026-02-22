# Phase 3: Job Notifications + Real-Time SSE Progress

## Phase Goal

Build two features that eliminate the need for users to keep a browser tab open during long jobs. **Job Notifications** sends email alerts (via SES) and webhook POST requests when jobs reach terminal states (completed, failed, budget exceeded). **Real-Time Progress via SSE** replaces the current 5-second polling with Server-Sent Events streamed from a Lambda function, providing instant progress updates for active jobs.

**Success criteria:**
- Users can configure email and webhook notification preferences in the Settings page
- Job completion/failure/budget-exceeded triggers notifications to configured destinations
- SSE endpoint streams real-time job progress (records_generated, cost, status) to the frontend
- Frontend uses EventSource instead of polling for active jobs
- All new code has unit tests; coverage remains above 70%

**Estimated tokens:** ~50,000

---

## Prerequisites

- Phase 2 complete
- Understanding of the Step Functions state machine terminal states (MarkJobCompleted, MarkJobFailed, MarkJobBudgetExceeded)
- Understanding of API Gateway HTTP API and Lambda response streaming
- Understanding of the current polling mechanism in `useJobPolling.ts` (5s/15s intervals)

---

## Task 1: Notification Preferences — Backend

**Goal:** Create a DynamoDB table and CRUD endpoints for storing per-user notification preferences (email enabled, webhook URL).

**Files to Modify/Create:**
- `backend/shared/models.py` — New `NotificationPreferences` Pydantic model
- `backend/lambdas/settings/get_preferences.py` — New Lambda handler
- `backend/lambdas/settings/update_preferences.py` — New Lambda handler
- `backend/template.yaml` — New table, functions, routes
- `tests/unit/test_notification_preferences.py` — Unit tests

**Prerequisites:**
- Understanding of existing Pydantic model patterns in `shared/models.py`

**Implementation Steps:**

1. **New Pydantic model in `shared/models.py`:**
   ```python
   class NotificationPreferences(BaseModel):
       user_id: str
       email_enabled: bool = False
       email_address: str | None = None  # Defaults to Cognito email if None
       webhook_enabled: bool = False
       webhook_url: str | None = None
       notify_on_complete: bool = True
       notify_on_failure: bool = True
       notify_on_budget_exceeded: bool = True
       updated_at: datetime
   ```
   Add `to_table_item()` and `from_dynamodb()` methods following the pattern of `JobConfig`.

2. **New DynamoDB table in `template.yaml`:**
   - Table name: `plot-palette-NotificationPreferences-${Environment}`
   - PK: `user_id` (S)
   - No sort key (one preferences record per user)
   - PAY_PER_REQUEST billing
   - PITR enabled

3. **`get_preferences.py` handler:**
   - Route: `GET /settings/notifications`
   - Get item from NotificationPreferences table by `user_id`
   - If not found, return defaults (all disabled)
   - Return: `{ email_enabled, email_address, webhook_enabled, webhook_url, notify_on_complete, notify_on_failure, notify_on_budget_exceeded }`

4. **`update_preferences.py` handler:**
   - Route: `PUT /settings/notifications`
   - Request body: any subset of preference fields
   - Validate webhook URL format if provided (must start with `https://`)
   - Upsert: put_item with updated fields + `updated_at`
   - Return: updated preferences

**Verification Checklist:**
- [ ] GET returns defaults for user with no saved preferences
- [ ] PUT saves and returns updated preferences
- [ ] Webhook URL must be HTTPS (reject HTTP)
- [ ] Invalid webhook URL returns 400
- [ ] Each user has isolated preferences

**Testing Instructions:**

Write tests in `tests/unit/test_notification_preferences.py`:
```python
# 1. test_get_preferences_default — No saved prefs. Assert defaults returned.
# 2. test_get_preferences_saved — Saved prefs exist. Assert correct values.
# 3. test_update_preferences_success — PUT with email_enabled=true. Assert saved.
# 4. test_update_preferences_webhook_https — PUT with https:// URL. Assert success.
# 5. test_update_preferences_webhook_http — PUT with http:// URL. Assert 400.
# 6. test_update_preferences_partial — PUT with only one field. Assert other fields preserved.
```

**Commit Message Template:**
```
feat(lambdas): add notification preferences CRUD endpoints

- NotificationPreferences Pydantic model
- GET /settings/notifications returns user preferences
- PUT /settings/notifications upserts preferences
- Webhook URL must be HTTPS
```

---

## Task 2: Notification Dispatch — Backend

**Goal:** Create a Lambda function that sends notifications when jobs reach terminal states. This function is triggered by DynamoDB Streams on the Jobs table (or called by Step Functions terminal states).

**Files to Modify/Create:**
- `backend/lambdas/notifications/send_notification.py` — New Lambda handler
- `backend/template.yaml` — New function, SES permissions, DynamoDB stream trigger OR Step Functions task
- `tests/unit/test_send_notification.py` — Unit tests

**Prerequisites:**
- Task 1 complete (preferences table and model exist)
- Understanding of terminal states in Step Functions: MarkJobCompleted, MarkJobFailed, MarkJobBudgetExceeded

**Implementation Steps:**

**Trigger approach decision:** Use Step Functions integration rather than DynamoDB Streams. This is simpler — add a notification step after each terminal state in the state machine. The Lambda receives `{ job_id, status, user_id }` directly.

1. **`send_notification.py` handler:**
   - Input: `{ "job_id": str, "status": str, "user_id": str }` (from Step Functions)
   - Can also be invoked as API Gateway event (for testing)
   - Logic:
     a. Fetch notification preferences for `user_id`
     b. Check if notification is wanted for this status (e.g., `notify_on_complete` for COMPLETED)
     c. If email_enabled:
        - Fetch job details from Jobs table (for cost, records count)
        - Build email body: job status, records generated, cost, link to job detail page
        - Send via SES (or SNS) to `email_address` (or Cognito email)
        - Use a configurable `SENDER_EMAIL` env var for the from address
     d. If webhook_enabled:
        - POST to `webhook_url` with JSON body: `{ job_id, status, records_generated, cost_estimate, completed_at, template_id }`
        - Set timeout to 5 seconds, catch and log failures (don't fail the state machine)
     e. Return success (always succeed — notification failure should not affect job lifecycle)

2. **Step Functions state machine update:**
   - After `MarkJobCompleted`, `MarkJobFailed`, and `MarkJobBudgetExceeded` states:
   - Add a new state `SendNotification` that invokes the Lambda
   - Use `ResultPath: null` to discard the notification result (don't pollute state)
   - Add `Catch` block that transitions to the End state (notifications are best-effort)

3. **SES setup:**
   - For MVP: use SES in sandbox mode (requires verified email addresses)
   - Add `SENDER_EMAIL` parameter to SAM template
   - Add SES SendEmail IAM permission to the notification Lambda

**Design decision:** Webhook delivery is at-most-once with no retry. If the webhook endpoint is down, the notification is lost. This is acceptable for MVP. Future enhancement: add SQS dead-letter queue for failed webhooks.

**Verification Checklist:**
- [ ] Email sent when email_enabled and status matches preference
- [ ] Email NOT sent when email_enabled but status doesn't match (e.g., notify_on_complete=false)
- [ ] Webhook POST sent with correct JSON payload
- [ ] Webhook failure does not fail the state machine
- [ ] No notification sent when all preferences are disabled
- [ ] Handler handles missing preferences gracefully (no notification)

**Testing Instructions:**

Write tests in `tests/unit/test_send_notification.py`:
```python
# 1. test_send_email_on_complete — Email enabled, job completed. Assert SES send_email called.
# 2. test_skip_email_when_disabled — Email disabled. Assert SES not called.
# 3. test_skip_email_wrong_status — notify_on_failure=false, job failed. Assert SES not called.
# 4. test_send_webhook_on_failure — Webhook enabled, job failed. Assert requests.post called with correct JSON.
# 5. test_webhook_failure_handled — Webhook returns 500. Assert handler returns success anyway.
# 6. test_no_preferences_no_notification — No preferences saved for user. Assert no SES/webhook calls.
# 7. test_both_email_and_webhook — Both enabled. Assert both SES and webhook called.
```

Mock `boto3` SES client and `requests.post` for webhook.

**Commit Message Template:**
```
feat(lambdas): add notification dispatch for job terminal states

- send_notification Lambda triggered by Step Functions
- Email via SES with job summary
- Webhook POST with JSON payload
- Best-effort delivery (failures don't affect job lifecycle)
```

---

## Task 3: Settings Page — Frontend

**Goal:** Build the Settings page (currently a stub) with notification preference management.

**Files to Modify/Create:**
- `frontend/src/routes/Settings.tsx` — Rewrite from stub
- `frontend/src/services/api.ts` — New API functions + Zod schemas
- `frontend/src/routes/Settings.test.tsx` — Tests

**Prerequisites:**
- Task 1 complete (preferences endpoints exist)

**Implementation Steps:**

1. **API service additions:**
   - `fetchNotificationPreferences(): Promise<NotificationPreferences>`
   - `updateNotificationPreferences(prefs: Partial<NotificationPreferences>): Promise<NotificationPreferences>`
   - Zod schema for `NotificationPreferences`

2. **Settings page layout:**
   - Page title: "Settings"
   - Section: "Notification Preferences"
     - Toggle: "Email notifications" (checkbox/switch)
     - If email enabled: email address input (pre-filled with Cognito email, editable)
     - Toggle: "Webhook notifications" (checkbox/switch)
     - If webhook enabled: URL input with HTTPS validation
     - Checkboxes: "Notify on job completion", "Notify on job failure", "Notify on budget exceeded"
     - Save button (calls update API)
     - Success toast on save
   - Uses `useQuery` to fetch current preferences on mount
   - Uses `useMutation` to save changes

3. **Form behavior:**
   - Load current preferences into form state
   - Dirty tracking: only enable Save when form has changes
   - Optimistic update: show new values immediately, rollback on error
   - Validate webhook URL client-side before submission

**Verification Checklist:**
- [ ] Settings page loads and shows current preferences
- [ ] Toggle email enables/disables email notification fields
- [ ] Toggle webhook enables/disables webhook URL field
- [ ] Webhook URL requires HTTPS prefix
- [ ] Save button disabled when no changes
- [ ] Save persists preferences and shows success toast
- [ ] Error shows error toast

**Testing Instructions:**

Create `frontend/src/routes/Settings.test.tsx`:
```typescript
// 1. test: loads and displays current preferences
// 2. test: email toggle shows/hides email input
// 3. test: webhook toggle shows/hides URL input
// 4. test: rejects HTTP webhook URL
// 5. test: save button disabled when no changes
// 6. test: save calls API with updated preferences
// 7. test: shows success toast on save
// 8. test: shows error toast on save failure
```

**Commit Message Template:**
```
feat(frontend): build settings page with notification preferences

- Email notification toggle with address input
- Webhook notification toggle with HTTPS URL validation
- Event type checkboxes (complete, failure, budget exceeded)
- Dirty tracking and optimistic updates
```

---

## Task 4: SSE Progress Endpoint — Backend

**Goal:** Create a Lambda function that returns a Server-Sent Events stream for real-time job progress. The Lambda polls DynamoDB at short intervals and streams updates until the job reaches a terminal state.

**Files to Modify/Create:**
- `backend/lambdas/jobs/stream_progress.py` — New Lambda handler (response streaming)
- `backend/template.yaml` — New function with response streaming config
- `tests/unit/test_stream_progress.py` — Unit tests

**Prerequisites:**
- Understanding of Lambda response streaming: the handler writes to a `ResponseStream` object rather than returning a response dict
- Understanding of SSE format: `data: {json}\n\n`
- Understanding of API Gateway HTTP API support for Lambda response streaming

**Implementation Steps:**

1. **SSE Lambda handler:**
   - Route: `GET /jobs/{job_id}/stream`
   - This Lambda uses **Lambda Web Adapter** or **Function URL with response streaming** rather than API Gateway (API Gateway HTTP API does not natively support streaming responses)
   - **Alternative approach (simpler for SAM):** Use a Lambda Function URL with `InvokeMode: RESPONSE_STREAM` and proxy through CloudFront or expose directly
   - **Simplest approach for MVP:** Use a standard Lambda that returns the current state as SSE-formatted response. The frontend reconnects periodically via EventSource's built-in retry mechanism.

   **Recommended MVP approach — Polling SSE emulation:**
   - Lambda returns SSE-formatted response with `Content-Type: text/event-stream`
   - Response body: single SSE event with current job state
   - Frontend uses `EventSource` which auto-reconnects on connection close (default 3s retry)
   - This gives near-real-time updates without true streaming infrastructure
   - Set Lambda timeout to 15s (standard)

   Handler logic:
   a. Extract `job_id` from path parameters, `user_id` from JWT
   b. Fetch job from Jobs table, verify ownership
   c. Build progress event:
      ```
      data: {"job_id":"...","status":"RUNNING","records_generated":150,"cost_estimate":1.23,"budget_limit":10.0,"updated_at":"..."}

      ```
   d. Return with headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
   e. For terminal states, include `event: complete\ndata: {...}\n\n` to signal the frontend to close the connection

2. **Response format:**
   ```
   HTTP/1.1 200 OK
   Content-Type: text/event-stream
   Cache-Control: no-cache

   data: {"job_id":"abc","status":"RUNNING","records_generated":150,"tokens_used":7500,"cost_estimate":1.23,"budget_limit":10.0,"updated_at":"2026-02-22T12:00:00"}

   ```

   For terminal states:
   ```
   event: complete
   data: {"job_id":"abc","status":"COMPLETED","records_generated":500,...}

   ```

**Verification Checklist:**
- [ ] Returns Content-Type: text/event-stream
- [ ] Response body is valid SSE format
- [ ] Job ownership verified (403 for non-owner)
- [ ] Terminal state includes `event: complete`
- [ ] CORS headers included
- [ ] Returns 404 for nonexistent job

**Testing Instructions:**

Write tests in `tests/unit/test_stream_progress.py`:
```python
# 1. test_stream_running_job — Mock RUNNING job. Assert SSE data event with progress fields.
# 2. test_stream_completed_job — Mock COMPLETED job. Assert event: complete.
# 3. test_stream_not_owner — Different user_id. Assert 403.
# 4. test_stream_not_found — Nonexistent job. Assert 404.
# 5. test_stream_content_type — Assert Content-Type is text/event-stream.
# 6. test_stream_cache_control — Assert Cache-Control: no-cache header.
```

**Commit Message Template:**
```
feat(lambdas): add SSE progress streaming endpoint for jobs

- GET /jobs/{id}/stream returns text/event-stream
- Single-event SSE with auto-reconnect via EventSource
- Terminal states send event: complete signal
```

---

## Task 5: SSE Progress — Frontend Integration

**Goal:** Replace the 5-second polling in `useJobPolling` with EventSource-based SSE that auto-reconnects, providing near-real-time progress updates.

**Files to Modify/Create:**
- `frontend/src/hooks/useJobStream.ts` — New hook
- `frontend/src/hooks/useJobStream.test.ts` — Tests
- `frontend/src/routes/JobDetail.tsx` — Switch from useJobPolling to useJobStream
- `frontend/src/hooks/useJobPolling.ts` — Deprecate (keep for fallback)

**Prerequisites:**
- Task 4 complete (SSE endpoint exists)
- Understanding of the browser `EventSource` API

**Implementation Steps:**

1. **`useJobStream` hook:**
   ```typescript
   function useJobStream(jobId: string): {
     data: Job | undefined
     isConnected: boolean
     error: Error | null
   }
   ```
   - Creates `EventSource` connection to `${API_ENDPOINT}/jobs/${jobId}/stream`
   - Auth challenge: EventSource doesn't support custom headers
     - **Solution:** Pass token as query parameter: `?token=${idToken}`
     - The backend Lambda must check `queryStringParameters.token` as fallback when `Authorization` header is missing
   - On `message` event: parse JSON data, update React Query cache for `['job', jobId]`
   - On `complete` event: close EventSource, final cache update
   - On `error`: set error state, EventSource auto-reconnects (default 3s)
   - Cleanup: close EventSource on unmount or when job reaches terminal state
   - Return current job data from React Query cache

2. **Token in query parameter:**
   - Modify the SSE Lambda (Task 4) to also accept `token` query parameter
   - Parse JWT manually or call Cognito to verify (simpler: add a thin auth check)
   - For MVP: trust the token from query param since API Gateway authorizer may not work with EventSource's non-configurable headers

3. **JobDetail integration:**
   - Replace `useJobPolling(jobId)` with `useJobStream(jobId)`
   - Keep `useJobPolling` as fallback: if SSE connection fails 3 times, fall back to polling
   - Show connection status indicator: green dot for connected, yellow for reconnecting

4. **React Query cache integration:**
   - When SSE data arrives, update the query cache directly:
     ```typescript
     queryClient.setQueryData(['job', jobId], (old) => ({ ...old, ...sseData }))
     ```
   - This keeps all components that read `['job', jobId]` in sync without refetching

**Verification Checklist:**
- [ ] EventSource connects to SSE endpoint
- [ ] Job progress updates appear in real-time (no 5s delay)
- [ ] EventSource auto-reconnects on connection close
- [ ] Connection closed when job reaches terminal state
- [ ] Falls back to polling if SSE fails repeatedly
- [ ] Token passed as query parameter for auth
- [ ] Connection status indicator shown
- [ ] EventSource cleaned up on component unmount

**Testing Instructions:**

Create `frontend/src/hooks/useJobStream.test.ts`:

Mock EventSource:
```typescript
class MockEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  close = vi.fn()
  addEventListener = vi.fn()
  readyState = 1 // OPEN

  // Helper to simulate SSE message
  simulateMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent)
  }
}

vi.stubGlobal('EventSource', MockEventSource)
```

Tests:
```typescript
// 1. test: creates EventSource with correct URL including token
// 2. test: updates React Query cache on message
// 3. test: closes EventSource on terminal status
// 4. test: closes EventSource on unmount
// 5. test: sets isConnected to true when open
// 6. test: sets error on EventSource error
```

**Commit Message Template:**
```
feat(frontend): replace polling with SSE-based real-time job progress

- useJobStream hook with EventSource
- Auto-reconnect with polling fallback
- React Query cache integration for instant UI updates
- Connection status indicator on JobDetail
```

---

## Task 6: Infrastructure Updates for Phase 3

**Goal:** Add all new resources to the SAM template: notification preferences table, notification Lambda, settings Lambdas, SSE Lambda, SES permissions, and Step Functions updates.

**Files to Modify/Create:**
- `backend/template.yaml` — New tables, functions, routes, permissions
- `backend/infrastructure/step-functions/job-lifecycle.asl.json` — Add notification states
- `backend/lambdas/jobs/create_job.py` — Add `user_id` to SFN input
- `backend/lambdas/settings/` — New directory (create with `__init__.py`)
- `backend/lambdas/notifications/` — New directory (create with `__init__.py`)

**Prerequisites:**
- All handler code from Tasks 1-4 exists

**Implementation Steps:**

1. **Create new Lambda directories:**
   - `mkdir -p backend/lambdas/settings && touch backend/lambdas/settings/__init__.py`
   - `mkdir -p backend/lambdas/notifications && touch backend/lambdas/notifications/__init__.py`
   - These directories need `__init__.py` to match the existing pattern (all Lambda subdirectories have them).

2. **NotificationPreferences table (in `backend/template.yaml`):**
   - Name: `plot-palette-NotificationPreferences-${Environment}`
   - PK: `user_id` (S)
   - PAY_PER_REQUEST, PITR enabled

3. **New Lambda functions (in `backend/template.yaml`):**
   - `GetPreferencesFunction`: `GET /settings/notifications`, DynamoDB read on NotificationPreferences
   - `UpdatePreferencesFunction`: `PUT /settings/notifications`, DynamoDB write on NotificationPreferences
   - `SendNotificationFunction`: No API route (invoked by Step Functions), DynamoDB read on Jobs + NotificationPreferences, SES SendEmail, outbound HTTPS for webhooks
   - `StreamProgressFunction`: `GET /jobs/{job_id}/stream`, DynamoDB read on Jobs

4. **SES permissions (in `backend/template.yaml`):**
   - Add IAM policy: `ses:SendEmail` on `*` (or restrict to verified domain)
   - Add `SENDER_EMAIL` parameter to template

5. **Propagate `user_id` through the state machine:**

   The state machine currently receives `{ job_id, retry_count }` from `create_job.py` (line ~110). Two changes are required:

   **a. Modify `backend/lambdas/jobs/create_job.py`** — Add `user_id` to the SFN start_execution input:
   ```python
   # Change from:
   input=json.dumps({"job_id": job_id, "retry_count": 0}),
   # Change to:
   input=json.dumps({"job_id": job_id, "user_id": user_id, "retry_count": 0}),
   ```

   **b. Modify `backend/infrastructure/step-functions/job-lifecycle.asl.json`** — The `IncrementRetryCount` Pass state (lines 167-174) currently only preserves `job_id` and `retry_count`:
   ```json
   "IncrementRetryCount": {
     "Type": "Pass",
     "Parameters": {
       "job_id.$": "$.job_id",
       "retry_count.$": "States.MathAdd($.retry_count, 1)"
     },
     "Next": "CheckMaxRetries"
   }
   ```
   **This will strip `user_id` from the state after any Spot interruption retry.** Add `user_id` passthrough:
   ```json
   "IncrementRetryCount": {
     "Type": "Pass",
     "Parameters": {
       "job_id.$": "$.job_id",
       "user_id.$": "$.user_id",
       "retry_count.$": "States.MathAdd($.retry_count, 1)"
     },
     "Next": "CheckMaxRetries"
   }
   ```

6. **Add notification states to `backend/infrastructure/step-functions/job-lifecycle.asl.json`:**

   The state machine is defined in JSON (ASL format), NOT in the SAM template YAML. All state machine edits go in this file.

   After each terminal state, change `"End": true` to `"Next": "SendNotification{Status}"` and add a notification state. Example for MarkJobCompleted:

   **Change MarkJobCompleted** (currently ends the execution):
   ```json
   "MarkJobCompleted": {
     "Type": "Task",
     "Resource": "arn:aws:states:::dynamodb:updateItem",
     "Parameters": { ... },
     "ResultPath": null,
     "Next": "SendNotificationCompleted"
   }
   ```

   **Add SendNotificationCompleted:**
   ```json
   "SendNotificationCompleted": {
     "Type": "Task",
     "Resource": "${SendNotificationFunctionArn}",
     "Parameters": {
       "job_id.$": "$.job_id",
       "user_id.$": "$.user_id",
       "status": "COMPLETED"
     },
     "ResultPath": null,
     "Catch": [
       {
         "ErrorEquals": ["States.ALL"],
         "ResultPath": null,
         "Next": "EndCompleted"
       }
     ],
     "Next": "EndCompleted"
   },
   "EndCompleted": {
     "Type": "Succeed"
   }
   ```

   Repeat the pattern for `MarkJobFailed` → `SendNotificationFailed` → `EndFailed` and `MarkJobBudgetExceeded` → `SendNotificationBudgetExceeded` → `EndBudgetExceeded`.

   **Note:** The `${SendNotificationFunctionArn}` substitution variable must be added to the SAM template where it passes substitutions to the ASL definition file.

7. **Add `NOTIFICATION_PREFERENCES_TABLE_NAME` to Globals environment in `backend/template.yaml`.**

8. **SSE endpoint considerations:**
   - API Gateway HTTP API standard Lambda integration works for single-response SSE
   - Response headers must include `Content-Type: text/event-stream`
   - The Lambda response format is the standard `{ statusCode, headers, body }` dict

**Verification Checklist:**
- [ ] `cfn-lint backend/template.yaml` passes
- [ ] NotificationPreferences table defined correctly
- [ ] `backend/lambdas/settings/__init__.py` exists
- [ ] `backend/lambdas/notifications/__init__.py` exists
- [ ] `create_job.py` SFN input includes `user_id`
- [ ] `IncrementRetryCount` in ASL passes through `user_id`
- [ ] ASL has notification states after each terminal state (3 total)
- [ ] SES permissions granted to notification Lambda
- [ ] SENDER_EMAIL parameter added
- [ ] All new Lambdas have correct routes and policies

**Commit Message Template:**
```
feat(infra): add notification infrastructure and SSE streaming endpoint

- NotificationPreferences DynamoDB table
- Settings, notification dispatch, and SSE Lambda functions
- Step Functions notification steps after terminal states
- SES SendEmail permissions
```

---

## Task 7: Integration Tests for Phase 3

**Goal:** Integration tests for notification dispatch and SSE streaming.

**Files to Modify/Create:**
- `tests/integration/test_notifications.py` — Integration tests
- `tests/integration/test_sse_progress.py` — Integration tests

**Prerequisites:**
- Tasks 1-4 complete

**Implementation Steps:**

1. **Notification dispatch integration test:**
   - Create NotificationPreferences and Jobs tables with moto
   - Insert preferences with email_enabled=true for user A
   - Insert completed job for user A
   - Invoke send_notification handler with `{ job_id, status: "COMPLETED", user_id: "user-a" }`
   - Assert SES send_email was called (mock SES with moto)
   - Test with preferences disabled — assert SES not called

2. **SSE progress integration test:**
   - Create Jobs table with moto
   - Insert RUNNING job
   - Invoke stream_progress handler
   - Parse response body as SSE
   - Assert `data:` line contains valid JSON with correct fields
   - Test terminal state — assert `event: complete` line present

**Verification Checklist:**
- [ ] Notification sends email when preferences say to
- [ ] Notification skips when preferences say not to
- [ ] SSE response is valid format
- [ ] SSE terminal event sent for completed jobs

**Commit Message Template:**
```
test(integration): add notification dispatch and SSE progress tests

- Notification: email sent/skipped based on preferences
- SSE: valid event stream format, terminal event signaling
```

---

## Phase Verification

After completing all tasks in Phase 3:

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
- SSE uses single-event-per-connection pattern (not true long-lived streaming). EventSource's built-in reconnect provides ~3s update intervals.
- Email requires SES verified sender. In sandbox mode, recipient must also be verified.
- Webhook delivery is at-most-once with no retry queue.
- Token in SSE query parameter is less secure than Authorization header. For production: consider Lambda Function URL with IAM auth or API Gateway WebSocket.
- Step Functions state machine changes require careful deployment (running executions use old definition).

### What Phase 4 Builds On
- Phase 4's batch job creation will reuse the notification system (notify on batch completion)
- Phase 4's seed data generation will use the template engine infrastructure
