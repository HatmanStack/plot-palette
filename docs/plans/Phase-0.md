# Phase 0: Architecture & Design Foundation

## Purpose

This phase documents all architectural decisions, design patterns, and technical rationale that apply across the entire implementation. **Read this completely before starting Phase 1.** This is not an implementation phase - it's a reference guide for all subsequent phases.

---

## Architecture Decision Records (ADRs)

### ADR-001: ECS Fargate Spot vs Kubernetes

**Decision:** Use ECS Fargate Spot instead of Kubernetes (EKS) for generation workers.

**Rationale:**
- **Cost:** EKS control plane costs $73/month minimum, Fargate Spot has no baseline cost
- **Simplicity:** ECS is more AWS-native, less operational overhead than K8s
- **Spot Economics:** Fargate Spot provides same 70% savings as K8s spot instances
- **Serverless:** No node management, automatic scaling
- **CloudFormation:** Simpler templates, faster deployment

**Trade-offs:**
- Less portable (ECS is AWS-specific)
- K8s has richer ecosystem, but unnecessary for this use case

**Implementation Impact:**
- Use ECS Task Definitions instead of K8s Deployments
- Leverage ECS capacity providers for Spot allocation
- Implement SIGTERM handlers for Fargate Spot interruptions (120-second warning)

---

### ADR-002: Custom VPC vs Default VPC

**Decision:** Deploy all resources in a custom VPC with public subnets.

**Rationale:**
- **Predictability:** Complete control over network configuration
- **Portability:** Works in any AWS account, even if default VPC is modified/deleted
- **Security:** Isolated network stack, easier to audit
- **No Cost Difference:** VPCs, subnets, and Internet Gateways are free
- **Growth Path:** Easy to add private subnets or VPC endpoints later

**Configuration:**
- **CIDR:** 10.0.0.0/16
- **Public Subnets:** 3 subnets across 3 AZs (10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24)
- **Internet Gateway:** Attached to VPC for outbound traffic
- **No NAT Gateway:** Using public subnets to avoid $32/month NAT costs

**Security:**
- Security groups restrict traffic (not network ACLs)
- Fargate tasks in public subnets have public IPs but controlled ingress
- All AWS API calls use HTTPS over internet gateway

---

### ADR-003: AWS Bedrock for LLM Inference

**Decision:** Use AWS Bedrock for all model inference instead of external APIs or self-hosted models.

**Rationale:**
- **Serverless:** Pay-per-token, no infrastructure management
- **Cost Alignment:** Matches opportunistic compute philosophy (no baseline costs)
- **Model Variety:** Access to Claude, Llama, Mistral, Cohere, Titan
- **Security:** Data stays in AWS, no third-party API exposure
- **Reliability:** AWS SLA and regional availability

**Model Selection Strategy (Smart Routing):**
- **Question Generation:** Use cost-efficient models (Llama 3.1 8B, Mistral 7B)
- **Answer Generation:** Use premium models (Claude Sonnet, Llama 70B)
- **Rationale:** Questions are simpler (seed data transformation), answers require reasoning

**Cost Comparison (per 1M tokens):**
- Llama 3.1 8B: ~$0.30 input / $0.60 output
- Claude Sonnet: ~$3.00 input / $15.00 output
- Savings: ~10x cheaper for question generation

**Retry Strategy:**
- Simple exponential backoff (2s, 4s, 8s)
- Max 3 retries per API call
- No model fallback (ADR-003a decided against it for consistency)

---

### ADR-004: S3-Only Storage with ETags

**Decision:** Use S3 exclusively for data storage (checkpoints, outputs, seed data) with ETag-based concurrency control.

**Rationale:**
- **Serverless:** No provisioned storage capacity
- **Cost:** $0.023/GB/month (cheapest option)
- **Durability:** 11 nines durability
- **Integration:** Native integration with all AWS services
- **Lifecycle:** Easy to configure Glacier archival

**ETag Usage:**
- **Checkpoint Writes:** Use conditional PUT with If-None-Match to prevent overwrites
- **Checkpoint Reads:** Use If-Match to ensure consistent read-modify-write
- **Pattern:** Read checkpoint → modify → write with ETag from read
- **Prevents:** Race conditions when multiple tasks resume same job

**Example Flow:**
```
1. Task reads checkpoint.json, gets ETag "abc123"
2. Task generates 50 records
3. Task writes updated checkpoint with If-Match: "abc123"
4. If ETag changed (another task updated), write fails → re-read and merge
```

**Storage Structure:**
```
s3://plot-palette-{stack-id}/
  seed-data/
    {user-id}/
      main_dictionary.json
      part1.json
      ...
  sample-datasets/
    poetry/...
    literature/...
  jobs/
    {job-id}/
      config.json
      checkpoint.json
      outputs/
        batch-001.jsonl
        batch-002.jsonl
      exports/
        dataset.jsonl
        dataset.parquet
        dataset.csv
```

---

### ADR-005: DynamoDB for State Management

**Decision:** Use DynamoDB for all stateful coordination (jobs, queue, progress, cost tracking).

**Rationale:**
- **Performance:** Single-digit millisecond latency
- **Consistency:** Strongly consistent reads for critical state
- **Serverless:** Pay-per-request pricing
- **Real-time:** Dashboard queries get instant updates
- **ACID:** Conditional writes prevent race conditions

**Tables:**

**1. Jobs Table**
- **PK:** `job-id` (UUID)
- **Attributes:** status, user-id, created-at, config, budget-limit, tokens-used, records-generated, cost-estimate
- **GSI:** user-id-index (query jobs by user)
- **Purpose:** Job metadata and progress tracking

**2. Queue Table**
- **PK:** `queue-id` (QUEUED, RUNNING, COMPLETED)
- **SK:** `job-id#timestamp`
- **Attributes:** priority, task-arn
- **Purpose:** Job queue management (FIFO within priority)

**3. Templates Table**
- **PK:** `template-id` (UUID)
- **SK:** `version` (for versioning)
- **Attributes:** name, user-id, template-definition, schema-requirements
- **Purpose:** Custom prompt templates

**4. Cost Tracking Table**
- **PK:** `job-id`
- **SK:** `timestamp`
- **Attributes:** bedrock-tokens, fargate-hours, s3-operations, estimated-cost
- **Purpose:** Real-time cost accumulation (TTL: 90 days)

---

### ADR-006: Cognito for Authentication

**Decision:** Use Amazon Cognito User Pools for authentication and authorization.

**Rationale:**
- **Built-in:** User management, password policies, MFA, email verification
- **Integration:** Native HTTP API Gateway JWT authorizer support
- **Scalable:** Handles millions of users
- **Security:** Industry-standard OAuth 2.0 / OIDC
- **Cost:** 50,000 MAUs free tier, $0.0055/MAU after

**Configuration:**
- **Password Policy:** Min 12 chars, uppercase, lowercase, number, special char
- **MFA:** Optional (user choice)
- **Email Verification:** Required
- **Token Expiration:** Access token 1 hour, refresh token 30 days
- **Custom Attributes:** `user-role` (admin, user)

**User Flow:**
1. User signs up via React UI → Cognito User Pool
2. Email verification required
3. User logs in → receives JWT tokens (id, access, refresh)
4. React stores tokens in localStorage
5. API calls include Authorization: Bearer {access_token}
6. API Gateway validates JWT before invoking Lambda

---

### ADR-007: HTTP API Gateway (not REST API)

**Decision:** Use HTTP API Gateway instead of REST API Gateway.

**Rationale:**
- **Cost:** ~71% cheaper ($1.00 vs $3.50 per million requests)
- **Performance:** Lower latency
- **JWT Authorizer:** Native Cognito integration
- **Simplicity:** Easier to configure than REST API
- **Sufficient:** No need for REST API advanced features (request validation, usage plans)

**Endpoints:**
- `POST /jobs` - Create generation job
- `GET /jobs` - List user's jobs
- `GET /jobs/{id}` - Get job details
- `DELETE /jobs/{id}` - Cancel/delete job
- `POST /templates` - Create prompt template
- `GET /templates` - List templates
- `PUT /templates/{id}` - Update template
- `POST /seed-data` - Upload seed data (returns presigned S3 URL)
- `GET /dashboard/{job-id}` - Real-time job stats

**CORS:** Enabled for Amplify-hosted frontend domain

---

### ADR-008: Amplify Hosting for Frontend

**Decision:** Use AWS Amplify Hosting for React SPA instead of S3+CloudFront.

**Rationale:**
- **Managed:** Automatic HTTPS, CDN, atomic deployments
- **Cost:** ~$1-2/month for small SPA (negligible difference from S3+CloudFront)
- **Simplicity:** One CloudFormation resource vs multiple (S3, CloudFront, OAI)
- **CI/CD Ready:** Future GitHub integration if needed

**Configuration:**
- Build command: `npm run build`
- Output directory: `dist` (Vite default)
- Environment variables: API_ENDPOINT, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID

---

### ADR-009: Python 3.13 Runtime

**Decision:** Use Python 3.13 for all Lambda functions and ECS tasks.

**Rationale:**
- **Consistency:** Same language as current Plot Palette codebase
- **Performance:** 3.13 has improved async performance
- **Libraries:** Rich ecosystem (boto3, requests, pandas for Parquet)
- **Typing:** Enhanced type hints for better IDE support
- **Lambda Support:** AWS supports 3.13 runtime

**Key Libraries:**
- `boto3` - AWS SDK
- `requests` - HTTP client (for Bedrock API)
- `pyarrow` - Parquet export
- `pandas` - Data manipulation for CSV export
- `jsonschema` - Schema validation
- `jinja2` - Template engine (for prompt templates)

---

### ADR-010: Nested CloudFormation Stacks

**Decision:** Use nested stacks instead of monolithic template.

**Rationale:**
- **Modularity:** Each stack focuses on one concern (network, compute, auth, storage)
- **Reusability:** Stacks can be updated independently
- **Limits:** Avoid 500-resource CloudFormation limit
- **Clarity:** Easier to understand and maintain

**Stack Structure:**
```
master-stack.yaml
  ├── network-stack.yaml (VPC, subnets, IGW)
  ├── storage-stack.yaml (S3 buckets)
  ├── database-stack.yaml (DynamoDB tables)
  ├── auth-stack.yaml (Cognito User Pool)
  ├── api-stack.yaml (API Gateway, Lambda functions)
  ├── compute-stack.yaml (ECS cluster, task definitions, capacity provider)
  └── frontend-stack.yaml (Amplify app)
```

**Parameters:** Master stack takes user inputs, passes to nested stacks
**Outputs:** Each stack exports values for cross-stack references

---

### ADR-011: Checkpoint Strategy - Hybrid Batch + Interruption

**Decision:** Checkpoint every N records (batch) + always checkpoint on Spot interruption signal.

**Rationale:**
- **Efficiency:** Batch checkpoints reduce S3 API costs (fewer PUTs)
- **Safety:** Spot interruption handler ensures no data loss
- **Balance:** N=50 provides good balance (2-5 minutes of work)

**Implementation:**
```python
# Pseudo-code
records_generated = 0
CHECKPOINT_INTERVAL = 50

def generate_loop():
    signal.signal(signal.SIGTERM, handle_interruption)

    while not budget_exceeded():
        record = generate_record()
        save_to_batch(record)
        records_generated += 1

        if records_generated % CHECKPOINT_INTERVAL == 0:
            checkpoint_to_s3()

def handle_interruption(signum, frame):
    checkpoint_to_s3()  # Save current progress
    sys.exit(0)
```

**Checkpoint Format (JSON):**
```json
{
  "job_id": "uuid",
  "records_generated": 1250,
  "current_batch": 25,
  "tokens_used": 450000,
  "cost_accumulated": 12.50,
  "last_updated": "2025-11-19T10:30:00Z",
  "resume_state": {
    "seed_data_index": 42,
    "template_step": "answer_generation"
  }
}
```

---

### ADR-012: Multi-Region Support

**Decision:** CloudFormation templates are region-agnostic and deployable in any AWS region.

**Rationale:**
- **Flexibility:** Users choose region based on data residency, latency, cost
- **Bedrock Availability:** Different regions have different model availability
- **Best Practice:** Portable infrastructure-as-code

**Implementation:**
- Use `AWS::Region` pseudo-parameter in templates
- Conditional logic for region-specific AMIs (not needed for Fargate)
- Documentation lists Bedrock-supported regions

**Recommended Regions:**
- us-east-1 (Virginia) - Broadest Bedrock model availability
- us-west-2 (Oregon) - Good Bedrock availability, lower cost
- eu-west-1 (Ireland) - European data residency

---

### ADR-013: Hard Budget Limits (No Throttling)

**Decision:** Jobs stop immediately when budget limit is reached. No dynamic throttling.

**Rationale:**
- **Predictability:** Users know exactly when job will stop
- **Simplicity:** No complex throttling algorithms
- **Control:** Users set precise limits, system enforces

**Implementation:**
- Every API call checks: `if cost_accumulated >= budget_limit: stop_job()`
- Checkpoint before stopping
- Set job status to `BUDGET_EXCEEDED`
- Send SNS notification (optional)

**Budget Tracking:**
```python
def calculate_cost(job_id):
    # Real-time calculation from DynamoDB Cost Tracking table
    bedrock_cost = tokens_used * COST_PER_TOKEN[model_id]
    fargate_cost = hours_running * FARGATE_SPOT_RATE[task_size]
    s3_cost = (puts + gets) * S3_API_COST
    return bedrock_cost + fargate_cost + s3_cost
```

---

### ADR-014: Data Lifecycle - Auto-Archive After 3 Days

**Decision:** S3 Lifecycle policy archives job outputs to Glacier after 3 days, metadata stays in DynamoDB.

**Rationale:**
- **Cost:** Glacier is ~90% cheaper than S3 Standard ($0.004/GB vs $0.023/GB)
- **Access Pattern:** Users typically use datasets immediately after generation
- **Retention:** Keep metadata forever for job history, archive raw data

**S3 Lifecycle Policy:**
```yaml
Rules:
  - Id: ArchiveJobOutputs
    Prefix: jobs/
    Status: Enabled
    Transitions:
      - Days: 3
        StorageClass: GLACIER_INSTANT_RETRIEVAL
    NoncurrentVersionTransitions:
      - Days: 1
        StorageClass: GLACIER_INSTANT_RETRIEVAL
```

**DynamoDB Metadata:**
- Jobs table keeps all job records (no TTL)
- Cost Tracking table uses TTL: 90 days (audit trail)
- Templates table: no expiration

**User Experience:**
- Dashboard shows archived status: "Archived to Glacier (restore takes 3-5 hours)"
- Restore button triggers S3 restore request
- Notification when restore complete

---

### ADR-015: Export Formats - JSONL, Parquet, CSV

**Decision:** Support three export formats with configurable partitioning.

**Rationale:**
- **JSONL:** Standard for LLM training (HuggingFace datasets default)
- **Parquet:** Efficient for large datasets, columnar storage, Spark/Athena compatible
- **CSV:** Universal compatibility, Excel, spreadsheets

**Partitioning Strategies:**
- By timestamp: `year=2025/month=11/day=19/`
- By category: `category=creative_writing/`, `category=poem/`
- Single file: All records in one file

**Implementation:**
- Export triggered when job completes (status = COMPLETED)
- Lambda function reads batch files from S3, converts format
- Parallel exports (all three formats simultaneously)

**File Naming:**
```
jobs/{job-id}/exports/
  dataset.jsonl
  dataset.parquet
  dataset.csv
  partitioned/
    timestamp/
      year=2025/month=11/day=19/records.jsonl
    category/
      creative_writing/records.jsonl
      poem/records.jsonl
```

---

### ADR-016: Prompt Template Engine Design

**Decision:** Jinja2-based template engine with custom extensions for LLM-specific features.

**Rationale:**
- **Familiarity:** Jinja2 is industry-standard (used by Ansible, Flask, etc.)
- **Power:** Supports variables, loops, conditionals, macros
- **Extensible:** Custom filters and functions for LLM operations
- **Safety:** Sandboxed execution

**Template Structure:**
```yaml
template:
  id: creative-writing-v1
  name: "Creative Writing Story Generator"
  version: 1

  schema_requirements:
    - author.biography
    - poem.text
    - day.notes

  steps:
    - id: outline
      model: llama-3.1-8b
      prompt: |
        Generate a story outline using:
        Author: {{ author.name }}
        Theme: {{ poem.text[:100] }}
        Setting: {{ day.notes | random_sentence }}

    - id: expand
      model: claude-sonnet
      prompt: |
        Expand this outline into a full story:
        {{ steps.outline.output }}

        Use {{ author.biography | writing_style }} style.

    - id: summary
      model: llama-3.1-8b
      prompt: |
        Summarize this story in 2 sentences:
        {{ steps.expand.output }}
```

**Custom Filters:**
- `random_sentence` - Extract random sentence from text
- `writing_style` - Analyze biography to extract writing style keywords
- `truncate_tokens` - Truncate to N tokens (not characters)

**Multi-Step Execution:**
- Steps execute sequentially
- Each step's output available to subsequent steps via `steps.{id}.output`
- Failure in any step stops execution, marks record as failed

**Conditional Logic:**
```jinja2
{% if author.genre == "poetry" %}
  Generate in verse form
{% else %}
  Generate in prose
{% endif %}
```

---

### ADR-017: Schema Auto-Detection from Templates

**Decision:** When users upload seed data, validate it has all fields required by their templates.

**Rationale:**
- **User-Centric:** Templates define what data is needed
- **Validation:** Catch missing fields before job starts
- **Flexibility:** No rigid schema, adapts to user needs

**Process:**
1. User creates template with variables: `{{ author.biography }}`, `{{ poem.text }}`
2. System parses template, extracts required fields: `["author.biography", "poem.text"]`
3. User uploads seed data JSON
4. System validates JSON has those nested fields
5. If validation fails, show error: "Missing required field: author.biography"

**Implementation:**
```python
def extract_schema(template_str):
    # Parse Jinja2 template, find all {{ variable }} references
    env = jinja2.Environment()
    ast = env.parse(template_str)
    variables = jinja2.meta.find_undeclared_variables(ast)
    return list(variables)

def validate_seed_data(data, required_fields):
    for field in required_fields:
        if not get_nested_field(data, field):
            raise ValidationError(f"Missing field: {field}")
```

---

### ADR-018: Concurrent Jobs with DynamoDB Queue

**Decision:** Support multiple concurrent jobs using DynamoDB as job queue.

**Rationale:**
- **Throughput:** Users can run multiple jobs simultaneously
- **Simplicity:** DynamoDB query for next job is straightforward
- **No SQS:** Avoid additional service, DynamoDB sufficient for this use case

**Queue Logic:**
```python
def get_next_job():
    # Query Queue table for QUEUED jobs, ordered by timestamp
    response = dynamodb.query(
        TableName='Queue',
        KeyConditionExpression='queue-id = :queued',
        ExpressionAttributeValues={':queued': 'QUEUED'},
        Limit=1,
        ScanIndexForward=True  # Oldest first (FIFO)
    )

    if response['Items']:
        job = response['Items'][0]
        # Atomic move to RUNNING
        dynamodb.update_item(
            TableName='Queue',
            Key={'queue-id': 'QUEUED', 'job-id#timestamp': job['sk']},
            UpdateExpression='SET queue-id = :running',
            ConditionExpression='queue-id = :queued'  # Prevent race
        )
        return job
```

**Concurrency Limit:**
- Parameter: `MaxConcurrentJobs` (default: 5)
- Count RUNNING jobs before starting new task
- If at limit, job stays QUEUED

---

### ADR-019: Smart Model Routing Implementation

**Decision:** Route generation steps to different models based on complexity and cost.

**Model Tiers:**
- **Tier 1 (Cheap):** Llama 3.1 8B, Mistral 7B - for simple transformations
- **Tier 2 (Balanced):** Llama 3.1 70B - for moderate complexity
- **Tier 3 (Premium):** Claude Sonnet - for complex reasoning

**Routing Rules:**
1. Question generation from seed data → Tier 1
2. Answer generation requiring reasoning → Tier 2 or Tier 3
3. Summarization, cleanup → Tier 1
4. Multi-step workflows → Mix based on step complexity

**Template Specification:**
```yaml
steps:
  - id: question
    model: llama-3.1-8b  # Explicit model

  - id: answer
    model_tier: premium  # Or: tier-1, tier-2, tier-3
                         # System picks best available model in tier
```

**Fallback:** If specified model unavailable (quota, throttling), no fallback - retry same model

---

### ADR-020: Consolidated IAM Roles

**Decision:** Use 3 IAM roles instead of 10+ granular roles.

**Rationale:**
- **Simplicity:** Easier to manage and debug
- **Sufficient:** Still follows least privilege for major components
- **Maintainability:** Fewer roles to update when adding features

**Roles:**

**1. ECSTaskRole**
- Bedrock InvokeModel
- S3 GetObject/PutObject (jobs/* prefix only)
- DynamoDB PutItem/UpdateItem (Jobs, Cost Tracking tables)
- CloudWatch PutLogEvents

**2. LambdaExecutionRole**
- S3 full access to bucket
- DynamoDB full access to all tables
- Cognito read access
- STS AssumeRole (for presigned URLs)
- CloudWatch PutLogEvents

**3. AmplifyServiceRole**
- S3 GetObject/PutObject (frontend bucket)
- CloudFormation read access (for nested stacks)

---

## Testing Strategy

### Unit Tests
- **Coverage Target:** 80% for business logic
- **Framework:** pytest for Python, Jest for React
- **Location:** `tests/unit/`
- **Run:** On every commit (pre-commit hook)

**What to Test:**
- Template parsing and validation
- Schema extraction from templates
- Cost calculation logic
- Checkpoint serialization/deserialization
- Budget enforcement logic
- Model routing decisions

### Integration Tests
- **Framework:** pytest with boto3 stubs (moto)
- **Location:** `tests/integration/`
- **Run:** Before merging to main

**What to Test:**
- DynamoDB operations (job creation, queue management)
- S3 checkpoint read/write with ETags
- Lambda function handlers (mocked API Gateway events)
- Bedrock API calls (mocked responses)

### End-to-End Tests
- **Framework:** Cypress for frontend, AWS SDK for backend
- **Location:** `tests/e2e/`
- **Run:** After CloudFormation deployment to test stack

**What to Test:**
- User signup → login → create job → monitor progress → download dataset
- Job cancellation
- Budget limit enforcement
- Spot interruption recovery (simulated)

### Performance Tests
- **Framework:** Locust (Python)
- **What to Test:**
- API Gateway throughput (1000 requests/sec)
- DynamoDB query latency
- ECS task startup time

---

## Common Patterns & Conventions

### Python Code Style
- **Formatter:** black (line length 100)
- **Linter:** ruff
- **Type Hints:** Use throughout (PEP 484)
- **Async:** Use `asyncio` for concurrent Bedrock calls in templates

### Error Handling
```python
class PlotPaletteError(Exception):
    """Base exception"""

class BudgetExceededError(PlotPaletteError):
    """Raised when job exceeds budget"""

class TemplateValidationError(PlotPaletteError):
    """Raised when template is invalid"""

# Always log errors before raising
logger.error(f"Budget exceeded for job {job_id}", exc_info=True)
raise BudgetExceededError(f"Job {job_id} exceeded budget")
```

### Logging
```python
import logging
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Structured logging (JSON for CloudWatch Insights)
logger.info(json.dumps({
    "event": "job_started",
    "job_id": job_id,
    "user_id": user_id,
    "timestamp": datetime.utcnow().isoformat()
}))
```

### Commit Messages
Follow Conventional Commits:
```
type(scope): subject

body

footer
```

**Types:** feat, fix, docs, test, refactor, chore
**Example:**
```
feat(templates): add multi-step template support

- Implement sequential step execution
- Add step output referencing
- Validate step dependencies

Closes #42
```

---

## Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | React | 18+ | UI framework |
| Frontend Build | Vite | 5+ | Build tool |
| Frontend Hosting | AWS Amplify | - | Static hosting + CDN |
| API Gateway | HTTP API | v2 | REST API |
| Auth | Cognito User Pools | - | Authentication |
| Backend Runtime | Python | 3.13 | Lambda + ECS |
| Compute | ECS Fargate Spot | - | Generation workers |
| LLM Inference | AWS Bedrock | - | Model APIs |
| Storage | S3 | - | Objects, checkpoints |
| Database | DynamoDB | - | State, queue, metadata |
| Orchestration | CloudFormation | - | Infrastructure as Code |
| Logging | CloudWatch Logs | - | Centralized logging |
| Template Engine | Jinja2 | 3.1+ | Prompt templates |

---

## Security Considerations

### Authentication & Authorization
- All API endpoints require valid Cognito JWT
- User can only access their own jobs (enforced in Lambda)
- S3 presigned URLs expire in 15 minutes
- No public bucket access

### Data Protection
- All data encrypted at rest (S3-SSE, DynamoDB encryption)
- All data encrypted in transit (HTTPS/TLS 1.2+)
- No sensitive data in CloudWatch logs
- IAM roles follow least privilege

### Network Security
- Security groups restrict Fargate task traffic
- API Gateway throttling: 1000 req/sec per user
- No SSH access to Fargate tasks (exec via ECS if needed)

### Secret Management
- Bedrock access via IAM roles (no API keys)
- Cognito User Pool client secret in Secrets Manager (not hardcoded)
- No credentials in CloudFormation templates

---

## Cost Optimization

### Expected Monthly Costs (Moderate Usage)
- **Fargate Spot:** $5-20 (depends on generation volume, 70% cheaper than on-demand)
- **Bedrock:** $10-100 (depends on token usage)
- **S3:** $1-5 (depends on dataset size)
- **DynamoDB:** $1-3 (on-demand pricing)
- **Amplify:** $1-2
- **API Gateway:** $0-1 (first 1M requests free)
- **Data Transfer:** $1-5
- **Total:** ~$20-140/month

### Cost Savings Strategies
1. Use Spot for all ECS tasks (70% savings)
2. Smart model routing (10x savings on simple tasks)
3. Glacier archival after 3 days (90% storage savings)
4. Hard budget limits prevent runaway costs
5. On-demand DynamoDB (pay per request, no provisioned capacity)

---

## Common Pitfalls to Avoid

### 1. Spot Interruptions Without Checkpoints
**Problem:** Losing hours of generation work when Spot task interrupted.
**Solution:** Always implement SIGTERM handler and checkpoint frequently.

### 2. ETag Race Conditions
**Problem:** Two tasks overwriting same checkpoint.
**Solution:** Always use If-Match when writing checkpoints.

### 3. Budget Tracking Lag
**Problem:** Job exceeds budget before check runs.
**Solution:** Check budget before every Bedrock call, not just periodically.

### 4. Large S3 Objects in Lambda
**Problem:** Lambda timeout/memory when processing large files.
**Solution:** Use streaming, process in chunks, or trigger Step Functions for large jobs.

### 5. Hardcoded Region Names
**Problem:** CloudFormation fails in other regions.
**Solution:** Always use `AWS::Region` pseudo-parameter.

### 6. Missing IAM Permissions
**Problem:** Tasks fail with AccessDenied errors.
**Solution:** Test IAM policies in dev before deploying.

### 7. Unbounded DynamoDB Scans
**Problem:** Slow queries, high costs.
**Solution:** Use Query with partition key, not Scan.

### 8. Forgetting CORS
**Problem:** Frontend can't call API.
**Solution:** Configure CORS on HTTP API for Amplify domain.

---

## Development Tools

### Recommended VSCode Extensions
- Python (Microsoft)
- Pylance (type checking)
- AWS Toolkit
- CloudFormation Linter
- ES7+ React/Redux/React-Native snippets
- Prettier (code formatter)

### AWS CLI Commands You'll Use
```bash
# Deploy CloudFormation
aws cloudformation create-stack --template-url ... --stack-name plot-palette

# Tail Lambda logs
aws logs tail /aws/lambda/plot-palette-api --follow

# Invoke Lambda locally
sam local invoke JobCreatorFunction --event events/create-job.json

# List ECS tasks
aws ecs list-tasks --cluster plot-palette --service-name generator

# Get Bedrock models
aws bedrock list-foundation-models --region us-east-1
```

### Local Development Setup
```bash
# Python virtualenv
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend
cd frontend
npm install
npm run dev  # Starts Vite dev server on http://localhost:5173

# Run tests
pytest tests/
npm test
```

---

## Phase 0 Complete

You've now reviewed all architectural decisions and design patterns. **No implementation in this phase** - this is purely reference material.

**Next Step:** Proceed to [Phase-1.md](./Phase-1.md) to begin implementation with core infrastructure setup.

**Remember:**
- Refer back to this document when making design decisions
- Follow the patterns and conventions defined here
- Avoid the common pitfalls listed
- Test continuously as you build

---

**Navigation:**
- [← Back to README](./README.md)
- [Next: Phase 1 - Core Infrastructure →](./Phase-1.md)
