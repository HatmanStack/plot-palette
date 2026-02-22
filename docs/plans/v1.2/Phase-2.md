# Phase 2: Cost Analytics Dashboard + Template Marketplace

## Phase Goal

Build two visibility and collaboration features. **Cost Analytics Dashboard** aggregates per-job cost data from the existing CostTracking table into user-facing charts and summaries — spend over time, cost per model tier, budget utilization trends. **Template Marketplace** completes the template sharing system by building a browsable, searchable library of public templates that users can preview and fork into their own collection.

**Success criteria:**
- Users see a cost analytics page with spend-over-time chart, per-model cost breakdown, and budget efficiency metrics
- Users can browse public templates, preview them, and fork (copy) them to their own account
- Template list page is fully functional (replacing the current "to be implemented" stub)
- All new code has unit tests; coverage remains above 70%

**Estimated tokens:** ~50,000

---

## Prerequisites

- Phase 1 complete (template version history and version list API work)
- Understanding of CostTracking table: PK=`job_id`, SK=`timestamp`, stores `estimated_cost` as `{bedrock, fargate, s3, total}`
- Understanding of Templates table: `is_public` field exists on all templates

---

## Task 1: Cost Aggregation Lambda

**Goal:** Create a new Lambda endpoint that queries the CostTracking table across all of a user's jobs and returns aggregated cost data suitable for chart rendering.

**Files to Modify/Create:**
- `backend/lambdas/dashboard/get_cost_analytics.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_cost_analytics.py` — Unit tests

**Prerequisites:**
- Understanding of CostTracking table structure and TTL (90-day retention)
- Understanding of Jobs table user-id-index GSI

**Implementation Steps:**

The handler should:

1. Extract `user_id` from JWT claims
2. Accept query parameters:
   - `period`: `7d`, `30d`, `90d` (default `30d`) — how far back to look
   - `group_by`: `day`, `week`, `model` (default `day`) — aggregation dimension
3. Query Jobs table by `user-id-index` to get all user job IDs
4. For each job ID, query CostTracking table to get cost records within the period
5. Aggregate data based on `group_by`:
   - **By day/week:** Group cost records by date, sum `{bedrock, fargate, s3, total}` per group
   - **By model:** Group by `model_id` field, sum costs per model
6. Also compute summary stats:
   - `total_spend`: Sum of all costs in period
   - `job_count`: Number of jobs in period
   - `avg_cost_per_job`: total_spend / job_count
   - `avg_cost_per_record`: total_spend / total_records
   - `budget_efficiency`: average (cost_estimate / budget_limit) across completed jobs
   - `most_expensive_job`: job_id with highest total cost
7. Return `{ summary, time_series, by_model }`

**Performance consideration:** The Jobs table query returns all user jobs, then we query CostTracking per job. For users with many jobs, this could be slow. Mitigate by:
- Filtering jobs by `created_at` within the period (the GSI sort key supports this)
- Using `ProjectionExpression` to fetch only needed fields
- Capping at 100 jobs max per query

**Verification Checklist:**
- [ ] Returns aggregated costs grouped by day
- [ ] Returns aggregated costs grouped by model
- [ ] Summary stats calculated correctly
- [ ] Period filter works (7d, 30d, 90d)
- [ ] Only returns data for the authenticated user's jobs
- [ ] Handles user with zero jobs gracefully (empty arrays, zero stats)
- [ ] Caps at 100 jobs to prevent timeout

**Testing Instructions:**

Write tests in `tests/unit/test_cost_analytics.py`:
```python
# 1. test_cost_analytics_by_day — Mock 3 jobs with cost records across 5 days. Assert daily totals.
# 2. test_cost_analytics_by_model — Mock cost records with different model_ids. Assert per-model sums.
# 3. test_cost_analytics_summary — Assert avg_cost_per_job, budget_efficiency calculated correctly.
# 4. test_cost_analytics_empty — User with no jobs. Assert empty arrays and zero stats.
# 5. test_cost_analytics_period_filter — Assert only jobs within 7d period returned.
# 6. test_cost_analytics_caps_at_100_jobs — Mock 150 jobs, assert only 100 processed.
```

**Commit Message Template:**
```
feat(lambdas): add cost analytics aggregation endpoint

- New GET /dashboard/cost-analytics endpoint
- Aggregates by day, week, or model
- Summary stats: total spend, avg cost, budget efficiency
- Caps at 100 jobs per query for performance
```

---

## Task 2: Cost Analytics Dashboard — Frontend Page

**Goal:** Build a new Cost Analytics page with spend-over-time chart, model cost breakdown, and summary cards. Use basic HTML/CSS charting (no chart library dependency).

**Files to Modify/Create:**
- `frontend/src/routes/CostAnalytics.tsx` — New page component
- `frontend/src/services/api.ts` — New API function + Zod schema
- `frontend/src/components/CostChart.tsx` — Bar chart component
- `frontend/src/components/CostSummaryCards.tsx` — Summary statistics cards
- `frontend/src/components/ModelCostBreakdown.tsx` — Per-model table
- `frontend/src/components/Sidebar.tsx` — Add navigation link
- `frontend/src/App.tsx` — Add route
- Tests for each new component

**Prerequisites:**
- Task 1 complete (cost analytics endpoint exists)

**Implementation Steps:**

1. **API service:**
   - `fetchCostAnalytics(period?: string, groupBy?: string): Promise<CostAnalytics>`
   - Zod schema:
     ```typescript
     const CostAnalyticsSchema = z.object({
       summary: z.object({
         total_spend: z.number(),
         job_count: z.number(),
         avg_cost_per_job: z.number(),
         avg_cost_per_record: z.number(),
         budget_efficiency: z.number(),
         most_expensive_job: z.string().nullable(),
       }),
       time_series: z.array(z.object({
         date: z.string(),
         bedrock: z.number(),
         fargate: z.number(),
         s3: z.number(),
         total: z.number(),
       })),
       by_model: z.array(z.object({
         model_id: z.string(),
         model_name: z.string().optional(),
         total: z.number(),
         job_count: z.number(),
       })),
     })
     ```

2. **CostSummaryCards component:**
   - 4 cards in a grid: Total Spend, Jobs Run, Avg Cost/Job, Budget Efficiency
   - Format costs with `$X.XX`
   - Format efficiency as percentage
   - Highlight total spend prominently

3. **CostChart component:**
   - Pure CSS bar chart (no chart library)
   - X-axis: dates. Y-axis: cost in dollars
   - Stacked bars: bedrock (blue), fargate (green), s3 (gray)
   - Hover/click shows tooltip with exact values
   - Responsive to container width
   - Implementation: CSS Grid with percentage-height div bars. Scale bars relative to max value in series.

4. **ModelCostBreakdown component:**
   - Table: Model Name, Total Cost, Job Count, Avg Cost/Job
   - Sorted by total cost descending
   - Map model IDs to friendly names (Claude 3.5 Sonnet, Llama 3.1 70B, etc.)
   - Use pricing constants from `frontend/src/constants/pricing.ts` for name mapping

5. **CostAnalytics page:**
   - Period selector: 7 days / 30 days / 90 days (buttons or dropdown)
   - Uses `useQuery({ queryKey: ['costs', 'analytics', period], ... })` with period in key for auto-refetch on change
   - Layout: Summary cards (top) → Time series chart (middle) → Model breakdown (bottom)
   - Loading skeleton while data fetches
   - Empty state for users with no cost data

6. **Navigation:**
   - Add "Cost Analytics" link to Sidebar (between Dashboard and Templates)
   - Add route `/cost-analytics` to App.tsx

**Verification Checklist:**
- [ ] Cost Analytics page loads and shows data
- [ ] Period selector changes data (7d/30d/90d)
- [ ] Bar chart renders with correct proportions
- [ ] Model breakdown table shows all models used
- [ ] Summary cards show correct formatted values
- [ ] Empty state shown for zero cost data
- [ ] Sidebar navigation link works
- [ ] Loading state shown while fetching

**Testing Instructions:**

Create tests for each component:
```typescript
// CostSummaryCards.test.tsx
// 1. test: renders all 4 summary cards with correct values
// 2. test: formats currency correctly ($1,234.56)
// 3. test: shows 0 values for empty data

// CostChart.test.tsx
// 4. test: renders correct number of bars
// 5. test: tallest bar gets 100% height
// 6. test: shows no bars for empty time_series

// ModelCostBreakdown.test.tsx
// 7. test: renders table with model rows sorted by cost
// 8. test: maps model IDs to friendly names
// 9. test: shows "No data" for empty array

// CostAnalytics.test.tsx
// 10. test: loads data on mount with default 30d period
// 11. test: switches period when button clicked
// 12. test: shows loading state
```

**Commit Message Template:**
```
feat(frontend): add cost analytics dashboard page

- CostSummaryCards, CostChart, ModelCostBreakdown components
- Pure CSS bar chart (no external chart library)
- Period selector (7d/30d/90d)
- Sidebar navigation link
```

---

## Task 3: Template Marketplace — Backend Search Endpoint

**Goal:** Create an endpoint for browsing and searching public templates. The existing `list_templates` endpoint returns public templates via scan, but doesn't support search, pagination, or sorting.

**Files to Modify/Create:**
- `backend/lambdas/templates/search_templates.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route + GSI
- `tests/unit/test_search_templates.py` — Unit tests

**Prerequisites:**
- Understanding that Templates table currently has GSI `user-id-index` but no GSI for public template discovery
- Understanding that DynamoDB scan with filter is expensive but acceptable for MVP (low template volume)

**Implementation Steps:**

1. **New `search_templates.py` handler:**
   - Route: `GET /templates/marketplace`
   - Query parameters:
     - `q`: search string (optional, matches against `name` and `description`)
     - `sort`: `popular` (most jobs), `recent` (newest), `name` (alphabetical) — default `recent`
     - `limit`: 1-50, default 20
     - `last_key`: pagination token (base64 JSON)
   - Implementation:
     - Scan Templates table with FilterExpression: `is_public = true`
     - For each template, keep only latest version (group by template_id, max version)
     - If `q` provided: case-insensitive substring match on `name` and `description`
     - Sort results in-memory based on `sort` parameter
     - Apply pagination (slice + build last_key)
   - Response includes: template_id, name, description, user_id, version, schema_requirements, step_count, created_at
   - Does NOT include `template_definition` (security: don't expose prompts in list view)

2. **Fork count tracking (lightweight approach):**
   - For `sort=popular`: count jobs referencing each template_id by scanning Jobs table
   - This is expensive — for MVP, skip the Jobs scan and sort by `created_at` for "popular" too
   - Add a TODO comment for future: add `fork_count` field to Templates table, increment on fork

**Design decision:** Full-text search in DynamoDB is limited. For MVP, client-side filtering via scan + filter is acceptable because the template volume is expected to be low (< 1000). If volume grows, migrate to OpenSearch or add a GSI on a `category` field.

**Verification Checklist:**
- [ ] Returns only public templates (no private templates leak)
- [ ] Search query filters by name and description (case-insensitive)
- [ ] Only latest version per template returned
- [ ] Response omits template_definition
- [ ] Pagination works with last_key
- [ ] Sort by recent works
- [ ] Empty search returns all public templates

**Testing Instructions:**

Write tests in `tests/unit/test_search_templates.py`:
```python
# 1. test_search_returns_only_public — Insert public and private templates. Assert only public returned.
# 2. test_search_query_filters_by_name — Search "poetry". Assert only matching template returned.
# 3. test_search_latest_version_only — Insert template with versions 1,2,3. Assert only version 3 in results.
# 4. test_search_pagination — Insert 25 templates, request limit=10. Assert 10 results + last_key.
# 5. test_search_no_template_definition — Assert template_definition not in any result item.
# 6. test_search_empty_results — Search query matching nothing. Assert empty array.
```

**Commit Message Template:**
```
feat(lambdas): add template marketplace search endpoint

- New GET /templates/marketplace with search, sort, pagination
- Returns only public templates, latest version per template
- Omits template_definition from response for security
```

---

## Task 4: Template Marketplace — Fork Endpoint

**Goal:** Create an endpoint that copies a public template into the authenticated user's collection, creating a new template with version 1.

**Files to Modify/Create:**
- `backend/lambdas/templates/fork_template.py` — New Lambda handler
- `backend/template.yaml` — New function resource + API route
- `tests/unit/test_fork_template.py` — Unit tests

**Prerequisites:**
- Understanding of create_template.py pattern for creating new templates
- Understanding that forked template should be independent (no link to original)

**Implementation Steps:**

1. **New `fork_template.py` handler:**
   - Route: `POST /templates/{template_id}/fork`
   - Request body (optional): `{ "name": "My copy of X" }` — override name, else use original name + " (fork)"
   - Logic:
     - Fetch source template (latest version) from Templates table
     - Verify source template is public OR owned by user (can fork your own)
     - Generate new `template_id` via `generate_template_id()`
     - Create new template item: copy `template_definition`, `schema_requirements`, `description`
     - Set `user_id` to authenticated user, `version` to 1, `is_public` to false
     - Set `name` to override or `"{original_name} (fork)"`
     - Put to Templates table with condition `attribute_not_exists(template_id)`
   - Return: `{ template_id, name, version, message: "Template forked successfully" }`

2. **No link tracking for MVP:**
   - Don't store "forked_from" reference. Keeps it simple.
   - The forked template is fully independent — editing the original doesn't affect the fork.

**Verification Checklist:**
- [ ] Fork creates a new template with new template_id
- [ ] Fork copies template_definition and schema_requirements
- [ ] Fork sets user_id to the authenticated user
- [ ] Fork sets version to 1 and is_public to false
- [ ] Fork fails on private template not owned by user (403)
- [ ] Fork allows custom name override
- [ ] Fork appends " (fork)" to name when no override

**Testing Instructions:**

Write tests in `tests/unit/test_fork_template.py`:
```python
# 1. test_fork_public_template_success — Fork a public template. Assert new template_id, user_id matches caller, version=1.
# 2. test_fork_private_template_not_owner — Attempt to fork another user's private template. Assert 403.
# 3. test_fork_own_template — Fork your own template. Assert success.
# 4. test_fork_custom_name — Provide name override. Assert new template uses it.
# 5. test_fork_default_name — No name override. Assert name is "{original} (fork)".
# 6. test_fork_not_found — Fork nonexistent template. Assert 404.
```

**Commit Message Template:**
```
feat(lambdas): add template fork endpoint

- New POST /templates/{id}/fork copies public template to user's collection
- Supports custom name override
- Fork is independent (no link to original)
```

---

## Task 5: Template Marketplace — Frontend Browse Page

**Goal:** Build the Template Marketplace page: a browsable, searchable gallery of public templates with preview and fork functionality. This replaces the "to be implemented" stub at `/templates`.

**Files to Modify/Create:**
- `frontend/src/routes/Templates.tsx` — Rewrite from stub to full page
- `frontend/src/services/api.ts` — New API functions + Zod schemas
- `frontend/src/components/TemplateCard.tsx` — New component
- `frontend/src/components/TemplatePreview.tsx` — New component (modal)
- `frontend/src/components/TemplateCard.test.tsx` — Tests
- `frontend/src/components/TemplatePreview.test.tsx` — Tests
- `frontend/src/routes/Templates.test.tsx` — Tests

**Prerequisites:**
- Tasks 3 and 4 complete (search and fork endpoints exist)

**Implementation Steps:**

1. **API service additions:**
   - `searchMarketplaceTemplates(params: { q?: string, sort?: string, limit?: number, lastKey?: string }): Promise<MarketplaceResults>`
   - `forkTemplate(templateId: string, name?: string): Promise<{ template_id: string }>`
   - Zod schemas for both

2. **Templates page layout:**
   - Two tabs at top: "My Templates" and "Marketplace"
   - **My Templates tab:**
     - Uses existing `list_templates` (fetch user's templates)
     - Grid of TemplateCard components
     - "Create Template" button → `/templates/new`
     - Delete button per template
   - **Marketplace tab:**
     - Search input at top
     - Sort dropdown: Recent, Name A-Z
     - Grid of TemplateCard components (public templates)
     - "Load More" button for pagination
     - Fork button per template

3. **TemplateCard component:**
   - Props: `{ template: MarketplaceTemplate, variant: 'owned' | 'marketplace', onFork?: () => void, onDelete?: () => void }`
   - Shows: name, description (truncated), step count, schema requirements as tags
   - **Owned variant:** Edit button → `/templates/{id}`, Delete button
   - **Marketplace variant:** Preview button (opens modal), Fork button
   - Created date shown as relative time

4. **TemplatePreview modal:**
   - Props: `{ templateId: string, onClose: () => void, onFork: () => void }`
   - Fetches full template detail via `fetchTemplate(templateId, { version: 'latest' })`
   - Shows: name, description, all steps with their prompts (read-only Monaco or pre-formatted), schema requirements
   - Fork button at bottom of modal
   - Close button / click-outside-to-close

5. **Fork flow:**
   - Click "Fork" → call `forkTemplate(templateId)`
   - On success: toast "Template forked", switch to "My Templates" tab, invalidate template query cache
   - On error: toast error message

**Verification Checklist:**
- [ ] My Templates tab shows user's templates
- [ ] Marketplace tab shows public templates
- [ ] Search filters marketplace results
- [ ] Fork creates copy in user's collection
- [ ] Preview modal shows template details
- [ ] "Create Template" navigates to editor
- [ ] Delete removes template (with confirmation)
- [ ] Pagination loads more results
- [ ] Empty states for no templates / no search results

**Testing Instructions:**

Create `frontend/src/components/TemplateCard.test.tsx`:
```typescript
// 1. test: renders template name and description
// 2. test: owned variant shows Edit and Delete buttons
// 3. test: marketplace variant shows Preview and Fork buttons
// 4. test: calls onFork when Fork clicked
// 5. test: truncates long descriptions
```

Create `frontend/src/components/TemplatePreview.test.tsx`:
```typescript
// 6. test: fetches and renders template details
// 7. test: shows all template steps
// 8. test: calls onFork when Fork button clicked
// 9. test: calls onClose when close button clicked
```

Create `frontend/src/routes/Templates.test.tsx`:
```typescript
// 10. test: renders My Templates tab with user templates
// 11. test: switches to Marketplace tab
// 12. test: search input triggers API call
// 13. test: fork success shows toast and switches tab
```

**Commit Message Template:**
```
feat(frontend): build template marketplace with browse, search, and fork

- Templates page with My Templates and Marketplace tabs
- TemplateCard component for owned and marketplace variants
- TemplatePreview modal for viewing template details
- Search, sort, and pagination for marketplace
- Fork flow with cache invalidation
```

---

## Task 6: Infrastructure Updates for Phase 2

**Goal:** Add all new Lambda functions to the SAM template.

**Files to Modify/Create:**
- `backend/template.yaml` — New function resources + API routes

**Prerequisites:**
- Tasks 1, 3, 4 handler code exists

**Implementation Steps:**

1. Add `GetCostAnalyticsFunction`:
   - Handler: `lambdas/dashboard/get_cost_analytics.lambda_handler`
   - Memory: 256 MB
   - Timeout: 15 seconds
   - Route: `GET /dashboard/cost-analytics`
   - Policies: DynamoDB read on Jobs table (GSI query), DynamoDB read on CostTracking table

2. Add `SearchTemplatesFunction`:
   - Handler: `lambdas/templates/search_templates.lambda_handler`
   - Memory: 256 MB
   - Timeout: 15 seconds
   - Route: `GET /templates/marketplace`
   - Policies: DynamoDB read on Templates table (scan with filter)

3. Add `ForkTemplateFunction`:
   - Handler: `lambdas/templates/fork_template.lambda_handler`
   - Memory: 256 MB
   - Timeout: 15 seconds
   - Route: `POST /templates/{template_id}/fork`
   - Policies: DynamoDB read/write on Templates table

**Verification Checklist:**
- [ ] `cfn-lint backend/template.yaml` passes
- [ ] New functions have correct routes
- [ ] IAM policies are least-privilege

**Commit Message Template:**
```
feat(infra): add SAM resources for cost analytics, marketplace, and fork

- GetCostAnalyticsFunction: GET /dashboard/cost-analytics
- SearchTemplatesFunction: GET /templates/marketplace
- ForkTemplateFunction: POST /templates/{id}/fork
```

---

## Task 7: Integration Tests for Phase 2

**Goal:** Write integration tests using moto for the cost analytics and marketplace features.

**Files to Modify/Create:**
- `tests/integration/test_cost_analytics.py` — Integration tests
- `tests/integration/test_marketplace.py` — Integration tests

**Prerequisites:**
- Tasks 1-4 complete

**Implementation Steps:**

1. **Cost analytics integration test:**
   - Create Jobs table with user-id-index GSI and CostTracking table
   - Insert 3 jobs for user A, 1 job for user B
   - Insert cost tracking records across 5 different days
   - Invoke handler as user A — verify only user A's data returned
   - Verify daily aggregation sums correctly
   - Verify summary stats (total, average, efficiency)

2. **Marketplace integration test:**
   - Create Templates table with correct PK/SK schema
   - Insert: 2 public templates (user A), 1 private template (user A), 1 public template (user B)
   - Search as user C — verify only 3 public templates returned
   - Search with query "poetry" — verify filtered results
   - Fork a public template as user C — verify new template in table with user C's user_id

**Verification Checklist:**
- [ ] Cost analytics returns correct data for authenticated user only
- [ ] Marketplace returns only public templates
- [ ] Fork creates independent copy

**Commit Message Template:**
```
test(integration): add cost analytics and marketplace integration tests

- Cost analytics: multi-user isolation, daily aggregation, summary stats
- Marketplace: public-only filtering, search, fork independence
```

---

## Phase Verification

After completing all tasks in Phase 2:

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
- Cost analytics aggregation scans CostTracking per-job (not ideal for heavy users with many jobs). Future optimization: pre-aggregate into a UserCostSummary table.
- Template marketplace search uses DynamoDB scan (no full-text index). Acceptable for < 1000 templates.
- Fork doesn't track lineage (no "forked from" field). Future feature if needed.
- No template categories or tags yet — search is substring match only.

### What Phase 3 Builds On
- Phase 3's notifications feature will add notification preference storage to the Settings page
- Phase 3's SSE progress streaming will integrate with the cost analytics (real-time cost updates)
