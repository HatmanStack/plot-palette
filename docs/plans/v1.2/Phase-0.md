# Phase 0: Foundation

## Phase Goal

Establish the architectural decisions, shared patterns, testing strategies, and deployment conventions that all subsequent phases inherit. No code is written in this phase — it is a reference document.

**Success criteria:** Every subsequent phase can reference this document for patterns, naming conventions, file locations, and testing approaches without ambiguity.

**Estimated tokens:** ~15,000

---

## Architecture Decisions

### ADR-1: API Pattern — Lambda per Endpoint

**Decision:** Each API endpoint is a separate Lambda function with its own handler file.

**Context:** The existing codebase follows this pattern. Each Lambda lives at `backend/lambdas/{domain}/{action}.py` (e.g., `backend/lambdas/jobs/create_job.py`). Every handler has the signature `lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]`.

**Rationale:** Individual Lambdas allow independent scaling, fine-grained IAM permissions, and isolated cold starts. The SAM template (`backend/template.yaml`) maps each Lambda to an API Gateway route.

**Implication for new features:** Every new API endpoint requires:
1. A new handler file in `backend/lambdas/{domain}/`
2. A new `AWS::Serverless::Function` resource in `backend/template.yaml`
3. Environment variables passed via the Globals section or per-function
4. IAM permissions for any DynamoDB tables or S3 buckets accessed

### ADR-2: DynamoDB Table Design — Single-Table-per-Entity

**Decision:** Each entity type gets its own DynamoDB table with on-demand (PAY_PER_REQUEST) billing.

**Context:** The codebase has 5 tables: Jobs (PK: `job_id`, GSI: `user_id+created_at`), Queue (PK: `status`, SK: `job_id_timestamp`), Templates (PK: `template_id`, SK: `version`, GSI: `user_id`), CostTracking (PK: `job_id`, SK: `timestamp`, TTL enabled), CheckpointMetadata (PK: `job_id`).

**Rationale:** On-demand billing matches the bursty Lambda access pattern. Single-table-per-entity keeps queries simple and avoids complex GSI overloading.

**Implication for new features:** New entity types (e.g., QualityMetrics, Batches, NotificationPreferences) get their own table defined in `backend/template.yaml`. Table names follow the pattern `plot-palette-{EntityName}-${Environment}` and are passed to Lambdas via environment variables.

### ADR-3: Frontend State — React Query for Server State, Context for Auth

**Decision:** Use React Query (`@tanstack/react-query`) for all server state. Use React Context only for authentication.

**Context:** The app uses `QueryClient` with `staleTime: 30_000`, `gcTime: 5 * 60_000`, `retry: 2`. Query keys follow the pattern `['entity']` for lists and `['entity', id]` for details. The `AuthContext` manages Cognito JWT tokens.

**Rationale:** React Query handles caching, deduplication, background refetch, and polling. Auth is a singleton concern that doesn't benefit from query semantics.

**Implication for new features:** New data fetching uses `useQuery`/`useMutation` hooks. New query keys must be unique and follow existing conventions. Cache invalidation uses `queryClient.invalidateQueries({ queryKey: ['entity'] })`.

### ADR-4: Authentication — Cognito JWT via API Gateway Authorizer

**Decision:** All API endpoints require Cognito JWT tokens validated by API Gateway's built-in JWT authorizer.

**Context:** The SAM template defines a `CognitoAuthorizer` on the HTTP API. User ID is extracted from JWT claims: `event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]`. Every Lambda verifies ownership before returning data.

**Rationale:** API Gateway handles token validation (signature, expiry, issuer, audience) before the Lambda is invoked. This eliminates auth boilerplate in handler code.

**Implication for new features:** All new endpoints automatically require auth via the default authorizer. To extract user ID in a new Lambda:
```python
user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
```

### ADR-5: Infrastructure as Code — SAM (Serverless Application Model)

**Decision:** All AWS resources are defined in `backend/template.yaml` using SAM.

**Context:** The template uses nested stacks, parameters for environment configuration (`Environment`, `CognitoUserPoolId`, `CognitoClientId`, `AllowedOrigins`, etc.), and SAM shorthand for Lambda functions.

**Rationale:** SAM extends CloudFormation with Lambda/API Gateway abstractions. The team already uses `sam build && sam deploy` for deployments.

**Implication for new features:** New DynamoDB tables, Lambda functions, SNS topics, and IAM roles are added to `backend/template.yaml`. Use existing parameter patterns for environment-specific values.

### ADR-6: Cost Tracking — Per-Job Breakdown with TTL

**Decision:** Cost data is stored in the CostTracking table with 90-day TTL auto-deletion.

**Context:** Each cost record has PK: `job_id`, SK: `timestamp`, and stores `estimated_cost` as a nested dict `{bedrock, fargate, s3, total}`. The worker writes cost records every `CHECKPOINT_INTERVAL` (50) records.

**Rationale:** TTL prevents unbounded table growth. Per-job granularity enables cost analytics. The worker is the single source of cost data.

**Implication for new features:** Cost analytics features aggregate from this table. New cost dimensions (e.g., quality scoring costs) should extend the existing `CostComponents` model rather than creating separate tables.

### ADR-7: Shared Modules — `backend/shared/`

**Decision:** All business logic shared between Lambdas and the worker lives in `backend/shared/`.

**Context:** Shared modules include: `models.py` (Pydantic models), `constants.py` (enums, pricing), `utils.py` (cost calculation, token estimation, S3 helpers), `lambda_responses.py` (HTTP response builders), `aws_clients.py` (boto3 client factory), `retry.py` (circuit breaker + backoff), `template_filters.py` (Jinja2 filters). Note: `template_engine.py` (prompt rendering + Bedrock calls) lives in `backend/ecs_tasks/worker/`, not in `shared/`.

**Rationale:** DRY. Lambda handlers are thin — they validate input, call shared logic, and format responses.

**Implication for new features:** New utility functions go in `backend/shared/utils.py`. New Pydantic models go in `backend/shared/models.py`. New constants go in `backend/shared/constants.py`. Only create new shared modules if the concern is clearly distinct from existing modules.

---

## Shared Patterns & Conventions

### Lambda Handler Pattern

Every Lambda handler follows this structure:

```python
"""
Module docstring describing the endpoint.
"""
import json
import sys
import os
from typing import Any

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.lambda_responses import success_response, error_response
from shared.aws_clients import get_dynamodb_resource
from shared.utils import extract_request_id, set_correlation_id

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    set_correlation_id(extract_request_id(event))

    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        # ... business logic ...
        return success_response(200, {"key": "value"})
    except KeyError:
        return error_response(400, "Missing required field")
    except Exception as e:
        return error_response(500, f"Internal error: {str(e)}")
```

**Key conventions:**
- `sys.path.insert(0, ...)` enables `from shared.xxx import yyy`
- `success_response(status_code, body_dict)` and `error_response(status_code, message)` from `lambda_responses.py`
- `CORS_HEADERS.copy()` is used internally (already fixed in lambda_responses.py)
- Error messages are sanitized before returning to clients
- All DynamoDB access uses `get_dynamodb_resource()` or `get_dynamodb_client()` from `aws_clients.py`

### DynamoDB Access Patterns

**Resource (high-level) for most operations:**
```python
dynamodb = get_dynamodb_resource()
table = dynamodb.Table(os.environ["JOBS_TABLE_NAME"])
table.get_item(Key={"job_id": job_id})
table.put_item(Item={...}, ConditionExpression="attribute_not_exists(job_id)")
table.update_item(Key={...}, UpdateExpression="SET #s = :s", ...)
table.query(IndexName="user-id-index", KeyConditionExpression=Key("user_id").eq(uid))
```

**Client (low-level) for transactional writes:**
```python
client = get_dynamodb_client()
client.transact_write_items(TransactItems=[...])
```

**Table name env vars:**
- `JOBS_TABLE_NAME` → `plot-palette-Jobs-{env}`
- `QUEUE_TABLE_NAME` → `plot-palette-Queue-{env}`
- `TEMPLATES_TABLE_NAME` → `plot-palette-Templates-{env}`
- `COST_TRACKING_TABLE_NAME` → `plot-palette-CostTracking-{env}`
- `CHECKPOINT_METADATA_TABLE_NAME` → `plot-palette-CheckpointMetadata-{env}`
- `BUCKET_NAME` → `plot-palette-data-{env}-{account_id}`

### S3 Key Patterns

```
seed-data/{user_id}/{filename}              # Uploaded seed data
jobs/{job_id}/checkpoint.json               # Checkpoint state
jobs/{job_id}/outputs/batch-{NNNN}.jsonl    # Intermediate batches (0-padded 4 digits)
jobs/{job_id}/exports/dataset.{ext}         # Final export (jsonl/parquet/csv)
```

### Frontend Component Pattern

```typescript
// Route page component
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '../contexts/ToastContext'
import { useAuth } from '../hooks/useAuth'

export default function PageName() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['entity'],
    queryFn: fetchEntity,
  })

  const mutation = useMutation({
    mutationFn: createEntity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entity'] })
      toast('Created successfully', 'success')
    },
    onError: (err) => {
      toast(err.message, 'error')
    },
  })

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  return (/* JSX */)
}
```

### API Service Pattern

```typescript
// In frontend/src/services/api.ts
export async function fetchEntity(): Promise<Entity[]> {
  const response = await apiClient.get('/entity')
  return EntityListSchema.parse(response.data).entities
}

export async function createEntity(data: CreateEntityInput): Promise<Entity> {
  const response = await apiClient.post('/entity', data)
  return EntitySchema.parse(response.data)
}
```

All API responses are validated with Zod schemas before being returned to components.

### Zod Schema Pattern

```typescript
const EntityBase = z.object({
  entity_id: z.string(),
  user_id: z.string().default(''),
  created_at: z.string().default(''),
  // ... fields with defaults for optional DynamoDB attributes
})

export const EntitySchema = EntityBase
export type Entity = z.infer<typeof EntitySchema>
```

### React Query Key Conventions

```typescript
['jobs']                    // Job list
['job', jobId]              // Single job
['templates']               // Template list
['template', templateId]    // Single template
// New features should follow:
['costs', jobId]            // Cost data for a job
['costs', 'aggregate']      // Aggregated cost data
['batches']                 // Batch list
['batch', batchId]          // Single batch
['quality', jobId]          // Quality scores for a job
```

---

## Testing Strategy

### Backend Tests

**Location:** `tests/` at repo root (not inside `backend/`)

**Framework:** pytest with markers (`unit`, `integration`, `worker`, `slow`)

**Running tests:**
```bash
# From repo root
PYTHONPATH=. pytest tests/unit tests/integration -v --tb=short
PYTHONPATH=. pytest tests/unit/test_specific.py -v                # Single file
PYTHONPATH=. pytest tests/unit/test_specific.py::TestClass::test_fn  # Single test
```

**Mocking approach:**
- **Unit tests:** `unittest.mock.MagicMock` for all AWS clients. Fixtures in `tests/conftest.py` provide pre-configured mocks.
- **Integration tests:** `moto` library for realistic AWS mocking (real boto3 calls against in-memory services).
- **E2E tests:** LocalStack in Docker (real DynamoDB/S3 over HTTP).

**New test file naming:** `tests/unit/test_{module}.py` or `tests/integration/test_{feature}.py`

**Fixture layering:**
1. `tests/conftest.py` — Mock AWS clients, env vars, sample user data
2. `tests/unit/conftest.py` — Sample Pydantic model instances
3. `tests/integration/conftest.py` — Real Cognito, real boto3 clients
4. `tests/e2e/conftest.py` — LocalStack provisioning, Lambda import shims

**Coverage:** 70% minimum (backend via pytest-cov)

**Testing Lambda handlers:**
```python
def test_handler_success(mock_dynamodb_client):
    """Build API Gateway v2 event, invoke handler, assert response."""
    event = {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": "user-123"}}},
            "http": {"method": "GET", "path": "/jobs"},
        },
        "pathParameters": {"job_id": "job-456"},
        "queryStringParameters": None,
        "body": None,
    }

    with patch("lambdas.jobs.get_job.get_dynamodb_resource") as mock_db:
        mock_table = MagicMock()
        mock_db.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {...}}

        response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["job_id"] == "job-456"
```

### Frontend Tests

**Location:** `frontend/src/**/*.test.{ts,tsx}` (co-located with source)

**Framework:** Vitest + Testing Library + jsdom

**Running tests:**
```bash
cd frontend
npx vitest run                          # All tests
npx vitest run src/services/api.test.ts # Single file
npx vitest run --coverage               # With coverage
```

**Mocking approach:**
- **API calls:** `vi.mock('../services/api')` + `vi.mocked(fn).mockResolvedValueOnce(...)`
- **Axios:** Module-level mock of `axios` with `create`, `get`, `post`, `delete`, `interceptors`
- **Auth:** `vi.mock('../services/auth')` or provider wrapper with mock context
- **Router:** `MemoryRouter` with `initialEntries` or `vi.mock('react-router-dom')`
- **React Query:** `createTestQueryClient()` with `retry: false, gcTime: 0`

**Custom render utility** (`src/test/test-utils.tsx`):
```typescript
customRender(ui, {
  authContext: mockAuthContextAuthenticated,
  initialEntries: ['/jobs/123'],
  withRouter: true,
  queryClient: createTestQueryClient(),
})
```

**Coverage:** 70% statements (vitest/v8)

**New test file naming:** Co-locate with source: `ComponentName.test.tsx`, `hookName.test.ts`, `serviceName.test.ts`

### TDD Workflow

For each task:
1. Write failing test(s) that define expected behavior
2. Implement minimum code to pass tests
3. Refactor if needed (tests must still pass)
4. Commit: `test(scope): add tests for X` then `feat(scope): implement X`

In practice, for Lambda handlers: write the test with mock event + expected response first, then implement the handler. For React components: write render + assertion tests first, then implement the component.

---

## Deployment Strategy

### SAM Template Additions

New resources are added to `backend/template.yaml`. Follow existing patterns:

**New DynamoDB table:**
```yaml
NewEntityTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub "plot-palette-NewEntity-${Environment}"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: entity_id
        AttributeType: S
    KeySchema:
      - AttributeName: entity_id
        KeyType: HASH
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
```

**New Lambda function:**
```yaml
NewActionFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: lambdas/domain/new_action.lambda_handler
    Runtime: python3.13
    MemorySize: 256
    Timeout: 15
    Policies:
      - DynamoDBCrudPolicy:
          TableName: !Ref NewEntityTable
    Environment:
      Variables:
        NEW_ENTITY_TABLE_NAME: !Ref NewEntityTable
    Events:
      Api:
        Type: HttpApi
        Properties:
          ApiId: !Ref HttpApi
          Method: GET
          Path: /new-entity
```

**Environment variable propagation:** Add table names to the Globals Environment section if the table is accessed by multiple Lambdas.

### Branch Strategy

Each phase should be developed on a feature branch: `feat/phase-{N}-{short-description}`. PRs merge to `main`.

---

## Commit Message Format

```
type(scope): brief description (>= 15 chars in subject)

- Detail 1
- Detail 2
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`, `build`

**Scopes:** `worker`, `lambdas`, `shared`, `frontend`, `infra`, `ci`, `docs`, `deps`

**Enforced by:** commitlint + pre-commit hook. Subject must be >= 15 characters. Scope is recommended (warning-level).

**Do NOT include:** `Co-Authored-By`, `Generated-By`, or any attribution lines.

---

## Key File Locations Reference

```
backend/
  template.yaml                          # SAM infrastructure definition
  lambdas/
    jobs/                                # Job CRUD handlers
      create_job.py, list_jobs.py, get_job.py, delete_job.py, download_job.py
    templates/                           # Template CRUD handlers
      create_template.py, list_templates.py, get_template.py,
      update_template.py, delete_template.py, test_template.py,
      import_template.py, export_template.py
    dashboard/
      get_stats.py                       # Job stats/cost endpoint
    seed_data/
      generate_upload_url.py, validate_seed_data.py
  shared/
    models.py                            # Pydantic models (JobConfig, TemplateDefinition, etc.)
    constants.py                         # Enums, pricing, config constants
    utils.py                             # Utilities (cost calc, token estimation, etc.)
    lambda_responses.py                  # success_response(), error_response()
    aws_clients.py                       # Boto3 client factory (LRU-cached)
    retry.py                             # CircuitBreaker + retry_with_backoff decorator
    template_filters.py                  # Custom Jinja2 filters
  ecs_tasks/worker/
    worker.py                            # ECS Worker class (generation loop, checkpoint, export)
    template_engine.py                   # TemplateEngine class (render + Bedrock calls)

frontend/src/
  App.tsx                                # Root: providers, router
  routes/                                # Page components
    Dashboard.tsx, CreateJob.tsx, JobDetail.tsx, Login.tsx, Signup.tsx,
    Templates.tsx (stub), TemplateEditor.tsx, Settings.tsx (stub)
  services/
    api.ts                               # Axios client + Zod-validated API functions
    auth.ts                              # Cognito auth wrapper
  contexts/
    AuthContext.tsx                       # Auth state provider
    ToastContext.tsx                      # Toast notification provider
  hooks/
    useAuth.ts, useJobs.ts, useJobPolling.ts
  components/
    Layout.tsx, Header.tsx, Sidebar.tsx, JobCard.tsx, StatusBadge.tsx,
    PrivateRoute.tsx, ErrorBoundary.tsx
  constants/
    pricing.ts                           # Client-side cost estimation
  test/
    setup.ts                             # Vitest global setup
    test-utils.tsx                       # Custom render with providers

tests/                                   # Backend tests (at repo root)
  conftest.py                            # Root fixtures
  unit/conftest.py                       # Unit fixtures
  integration/conftest.py                # Integration fixtures
  e2e/conftest.py                        # E2E fixtures
  fixtures/                              # Shared test data builders
```

---

## Pydantic Model Reference

Models the engineer will extend or reference frequently:

| Model | File | PK/SK | Key Fields |
|-------|------|-------|------------|
| `JobConfig` | `shared/models.py` | `job_id` | `user_id`, `status`, `config`, `budget_limit`, `records_generated`, `cost_estimate`, `execution_arn` |
| `TemplateDefinition` | `shared/models.py` | `template_id` / `version` | `name`, `user_id`, `steps`, `schema_requirements`, `is_public` |
| `TemplateStep` | `shared/models.py` | — | `id`, `model`, `model_tier`, `prompt` |
| `CheckpointState` | `shared/models.py` | — | `job_id`, `records_generated`, `tokens_used`, `cost_accumulated`, `etag` |
| `CostBreakdown` | `shared/models.py` | `job_id` / `timestamp` | `bedrock_tokens`, `fargate_hours`, `estimated_cost` (CostComponents), `model_id`, `ttl` |
| `CostComponents` | `shared/models.py` | — | `bedrock`, `fargate`, `s3`, `total` |
| `QueueItem` | `shared/models.py` | `status` / `job_id_timestamp` | `job_id`, `priority`, `task_arn` |

---

## Constants Reference

Key constants from `shared/constants.py` that new features will reference:

| Constant | Value | Usage |
|----------|-------|-------|
| `CHECKPOINT_INTERVAL` | 50 | Records between checkpoints |
| `COST_TRACKING_TTL_DAYS` | 90 | Auto-delete cost records after 90 days |
| `MAX_CONCURRENT_JOBS` | 5 | Not enforced yet (future use) |
| `PRESIGNED_URL_EXPIRATION` | 900 | 15-minute presigned URLs |
| `MODEL_PRICING` | dict | Per-model input/output pricing per 1M tokens |
| `MODEL_TIERS` | dict | Tier name → model ID mapping |
| `FARGATE_SPOT_PRICING` | dict | vCPU + memory hourly rates |
| `S3_PRICING` | dict | PUT/GET/DELETE per-operation costs |
| `EXPORT_FILE_NAMES` | dict | `{jsonl: "dataset.jsonl", parquet: "dataset.parquet", csv: "dataset.csv"}` |
| `S3_FOLDERS` | dict | Key prefix templates |
| `WORKER_EXIT_SUCCESS` | 0 | Normal completion |
| `WORKER_EXIT_ERROR` | 1 | Error exit |
| `WORKER_EXIT_BUDGET_EXCEEDED` | 2 | Budget limit reached |
