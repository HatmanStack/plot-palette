# Phase 1: Core Infrastructure Setup

## Phase Goal

Establish the foundational AWS infrastructure including VPC networking, S3 storage buckets, DynamoDB tables, and IAM roles. By the end of this phase, you will have all stateless infrastructure resources deployed and ready to support authentication, APIs, and compute workloads in subsequent phases.

**Success Criteria:**
- Custom VPC with 3 public subnets across 3 availability zones
- S3 bucket configured with lifecycle policies for Glacier archival
- 4 DynamoDB tables (Jobs, Queue, Templates, CostTracking) with appropriate indexes
- 3 IAM roles (ECSTask, Lambda, Amplify) with correct permissions
- All resources tested and validated via AWS CLI

**Estimated Tokens:** ~95,000

---

## Prerequisites

- **Phase 0** reviewed completely
- AWS CLI configured with credentials (`aws configure`)
- Python 3.13 installed and virtualenv created
- Git repository initialized
- AWS account with permissions to create VPC, S3, DynamoDB, IAM resources

---

## Project Structure Setup

Before implementing tasks, create the base project structure:

```
plot-palette/
├── infrastructure/
│   ├── cloudformation/
│   │   ├── master-stack.yaml         (Phase 7)
│   │   ├── network-stack.yaml        (Task 1)
│   │   ├── storage-stack.yaml        (Task 2)
│   │   ├── database-stack.yaml       (Task 3)
│   │   └── iam-stack.yaml            (Task 4)
│   └── scripts/
│       └── deploy.sh                 (Task 5)
├── backend/
│   ├── lambdas/                      (Phase 3)
│   ├── ecs_tasks/                    (Phase 4)
│   ├── shared/                       (Task 6)
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── constants.py
│   │   └── utils.py
│   └── requirements.txt              (Task 6)
├── frontend/                         (Phase 6)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   └── plans/                        (Exists)
└── README.md                         (Update in Task 7)
```

---

## Task 1: VPC and Networking Stack

### Goal

Create a custom VPC with public subnets across 3 availability zones, internet gateway, and security groups for Fargate tasks and VPC endpoints.

### Files to Create

- `infrastructure/cloudformation/network-stack.yaml` - VPC CloudFormation template

### Prerequisites

- AWS account must have available VPC quota (default: 5 VPCs per region)
- Confirm target region has at least 3 availability zones

### Implementation Steps

1. **Create the network CloudFormation template** with the following resources:
   - VPC with CIDR `10.0.0.0/16` and DNS hostnames enabled
   - Internet Gateway attached to VPC
   - 3 public subnets in different AZs:
     - Subnet A: `10.0.1.0/24` (us-east-1a, us-west-2a, etc.)
     - Subnet B: `10.0.2.0/24` (us-east-1b, us-west-2b, etc.)
     - Subnet C: `10.0.3.0/24` (us-east-1c, us-west-2c, etc.)
   - Route table for public subnets with route to IGW (`0.0.0.0/0 → IGW`)
   - Associate all 3 subnets with the public route table

2. **Create Security Groups:**
   - **ECSTaskSecurityGroup**: For Fargate tasks
     - Egress: Allow all outbound (0.0.0.0/0 on all ports) for Bedrock API, S3, DynamoDB
     - Ingress: None required (tasks don't receive inbound traffic)
   - **VPCEndpointSecurityGroup**: For future VPC endpoints (optional in Phase 1)
     - Ingress: Allow HTTPS (443) from VPC CIDR
     - Egress: Allow all outbound

3. **Add CloudFormation Outputs:**
   - VPC ID
   - All 3 subnet IDs (export with names for cross-stack reference)
   - Security Group IDs
   - Availability Zones used

4. **Use Intrinsic Functions:**
   - `Fn::GetAZs` to dynamically get AZs in the region
   - `Fn::Sub` for resource naming with stack name
   - Avoid hardcoding region-specific values

5. **Add Parameters:**
   - `EnvironmentName` (default: "production") - for resource tagging
   - Consider future expansion (no private subnets yet, but structure for adding them)

### Verification Checklist

- [ ] Template passes `aws cloudformation validate-template`
- [ ] VPC created with correct CIDR
- [ ] All 3 subnets created in different AZs
- [ ] Internet Gateway attached and route table configured
- [ ] Security groups created with correct rules
- [ ] Can ping 8.8.8.8 from a test EC2 instance in public subnet (manual test)
- [ ] All outputs exported correctly

### Testing Instructions

**Unit Test (Template Validation):**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/network-stack.yaml
```

**Integration Test (Deploy to AWS):**
```bash
aws cloudformation create-stack \
  --stack-name plot-palette-network-test \
  --template-body file://infrastructure/cloudformation/network-stack.yaml \
  --parameters ParameterKey=EnvironmentName,ParameterValue=test

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-network-test

# Verify outputs
aws cloudformation describe-stacks \
  --stack-name plot-palette-network-test \
  --query 'Stacks[0].Outputs'

# Cleanup
aws cloudformation delete-stack --stack-name plot-palette-network-test
```

### Commit Message Template

```
feat(infrastructure): add VPC and networking stack

- Create custom VPC with 10.0.0.0/16 CIDR
- Add 3 public subnets across availability zones
- Configure internet gateway and routing
- Create security groups for ECS tasks
- Export outputs for cross-stack references

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~8,000

---

## Task 2: S3 Storage Stack

### Goal

Create S3 bucket for all application data (seed data, job outputs, checkpoints) with lifecycle policies for Glacier archival and versioning enabled.

### Files to Create

- `infrastructure/cloudformation/storage-stack.yaml` - S3 bucket template

### Prerequisites

- Task 1 completed (VPC stack for potential VPC endpoint)
- S3 bucket names are globally unique - use pattern: `plot-palette-{AWS::AccountId}-{AWS::Region}`

### Implementation Steps

1. **Create S3 bucket with naming pattern** that ensures global uniqueness:
   - Use `Fn::Sub` to include account ID and region in bucket name
   - Enable versioning for checkpoints (ADR-004)
   - Enable server-side encryption (AES-256 or KMS)

2. **Configure lifecycle policies:**
   - **Rule 1 - Archive Job Outputs:**
     - Prefix: `jobs/*/outputs/`
     - Transition to GLACIER_INSTANT_RETRIEVAL after 3 days
     - Transition noncurrent versions to GLACIER after 1 day
   - **Rule 2 - Expire Incomplete Multipart Uploads:**
     - Abort after 7 days (cleanup)
   - **Rule 3 - Seed Data Retention:**
     - Prefix: `seed-data/`
     - No expiration (keep indefinitely)
     - Transition to INTELLIGENT_TIERING after 30 days (cost optimization)

3. **Configure CORS for presigned URLs:**
   - Allow origin: `*` (will be restricted to Amplify domain in Phase 6)
   - Allow methods: GET, PUT, POST, DELETE
   - Allow headers: `*`
   - Max age: 3600 seconds

4. **Create folder structure with prefix placeholders:**
   - Use S3 Object resource to create "folders":
     - `seed-data/.keep`
     - `sample-datasets/.keep`
     - `jobs/.keep`
   - Note: S3 doesn't have true folders, but this helps UI navigation

5. **Block Public Access:**
   - Enable all block public access settings (buckets are private)
   - Access only via presigned URLs and IAM roles

6. **Add CloudFormation Outputs:**
   - Bucket name
   - Bucket ARN
   - Bucket regional domain name

### Verification Checklist

- [ ] Bucket created with unique name including account ID
- [ ] Versioning enabled
- [ ] Encryption enabled (SSE-S3 or SSE-KMS)
- [ ] Lifecycle policies applied correctly
- [ ] CORS configuration allows required methods
- [ ] Public access blocked
- [ ] Can upload file via AWS CLI using IAM credentials
- [ ] Cannot access bucket without credentials

### Testing Instructions

**Unit Test:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/storage-stack.yaml
```

**Integration Test:**
```bash
# Deploy stack
aws cloudformation create-stack \
  --stack-name plot-palette-storage-test \
  --template-body file://infrastructure/cloudformation/storage-stack.yaml

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-storage-test

# Get bucket name from outputs
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-storage-test \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text)

# Test upload
echo "test" > /tmp/test.txt
aws s3 cp /tmp/test.txt s3://$BUCKET/jobs/test-job/outputs/test.txt

# Verify versioning
aws s3api list-object-versions --bucket $BUCKET --prefix jobs/test-job/

# Verify lifecycle policy
aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET

# Cleanup
aws s3 rm s3://$BUCKET/jobs/test-job/outputs/test.txt
aws cloudformation delete-stack --stack-name plot-palette-storage-test
```

### Commit Message Template

```
feat(infrastructure): add S3 storage bucket with lifecycle policies

- Create versioned S3 bucket with encryption
- Configure Glacier archival after 3 days for job outputs
- Add CORS configuration for presigned URLs
- Block public access, enforce IAM authentication
- Create logical folder structure

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~9,000

---

## Task 3: DynamoDB Tables Stack

### Goal

Create 4 DynamoDB tables (Jobs, Queue, Templates, CostTracking) with on-demand billing, encryption, and appropriate indexes.

### Files to Create

- `infrastructure/cloudformation/database-stack.yaml` - DynamoDB tables template

### Prerequisites

- Reviewed ADR-005 for table schemas
- Understanding of DynamoDB partition keys, sort keys, and GSIs

### Implementation Steps

1. **Create Jobs Table:**
   - **Partition Key:** `job_id` (String) - UUID
   - **Attributes:**
     - `user_id` (String)
     - `status` (String) - QUEUED, RUNNING, COMPLETED, FAILED, BUDGET_EXCEEDED, CANCELLED
     - `created_at` (String) - ISO 8601 timestamp
     - `updated_at` (String) - ISO 8601 timestamp
     - `config` (Map) - job configuration JSON
     - `budget_limit` (Number) - USD
     - `tokens_used` (Number)
     - `records_generated` (Number)
     - `cost_estimate` (Number) - USD
   - **GSI:** `user-id-index`
     - Partition Key: `user_id`
     - Sort Key: `created_at`
     - Projection: ALL
     - Purpose: Query all jobs for a user, sorted by creation date
   - **Billing:** On-demand
   - **Encryption:** AWS managed key

2. **Create Queue Table:**
   - **Partition Key:** `status` (String) - QUEUED, RUNNING, COMPLETED
   - **Sort Key:** `job_id#timestamp` (String) - Composite: `{job_id}#{timestamp}`
   - **Attributes:**
     - `job_id` (String)
     - `priority` (Number) - for future use
     - `task_arn` (String) - ECS task ARN when running
   - **Purpose:** FIFO queue within each status
   - **Billing:** On-demand
   - **Encryption:** AWS managed key

3. **Create Templates Table:**
   - **Partition Key:** `template_id` (String) - UUID
   - **Sort Key:** `version` (Number) - version number (1, 2, 3, ...)
   - **Attributes:**
     - `name` (String)
     - `user_id` (String)
     - `template_definition` (Map) - YAML/JSON template
     - `schema_requirements` (List) - ["author.biography", "poem.text"]
     - `created_at` (String)
     - `is_public` (Boolean) - if template is shareable
   - **GSI:** `user-id-index`
     - Partition Key: `user_id`
     - Projection: ALL
   - **Billing:** On-demand
   - **Encryption:** AWS managed key

4. **Create CostTracking Table:**
   - **Partition Key:** `job_id` (String)
   - **Sort Key:** `timestamp` (String) - ISO 8601
   - **Attributes:**
     - `bedrock_tokens` (Number)
     - `fargate_hours` (Number)
     - `s3_operations` (Number)
     - `estimated_cost` (Number) - USD
     - `model_id` (String) - which model was used
   - **TTL:** `ttl` attribute (90 days from timestamp)
   - **Purpose:** Time-series cost data for dashboard charts
   - **Billing:** On-demand
   - **Encryption:** AWS managed key

5. **Enable Point-in-Time Recovery** on all tables (backup/restore capability)

6. **Add CloudFormation Outputs:**
   - All table names
   - All table ARNs
   - GSI names

### Verification Checklist

- [ ] All 4 tables created with correct schemas
- [ ] Partition and sort keys defined correctly
- [ ] GSIs created on Jobs and Templates tables
- [ ] TTL enabled on CostTracking table
- [ ] Encryption enabled on all tables
- [ ] Point-in-time recovery enabled
- [ ] Can write and read items via AWS CLI
- [ ] GSI queries return expected results

### Testing Instructions

**Unit Test:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/database-stack.yaml
```

**Integration Test:**
```bash
# Deploy
aws cloudformation create-stack \
  --stack-name plot-palette-database-test \
  --template-body file://infrastructure/cloudformation/database-stack.yaml

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-database-test

# Test Jobs table
aws dynamodb put-item \
  --table-name plot-palette-Jobs \
  --item '{
    "job_id": {"S": "test-job-123"},
    "user_id": {"S": "user-456"},
    "status": {"S": "QUEUED"},
    "created_at": {"S": "2025-11-19T10:00:00Z"}
  }'

# Test GSI query
aws dynamodb query \
  --table-name plot-palette-Jobs \
  --index-name user-id-index \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid": {"S": "user-456"}}'

# Verify TTL on CostTracking
aws dynamodb describe-time-to-live \
  --table-name plot-palette-CostTracking

# Cleanup
aws dynamodb delete-item \
  --table-name plot-palette-Jobs \
  --key '{"job_id": {"S": "test-job-123"}}'

aws cloudformation delete-stack --stack-name plot-palette-database-test
```

### Commit Message Template

```
feat(infrastructure): add DynamoDB tables for jobs, queue, templates, costs

- Create Jobs table with user-id GSI for querying
- Create Queue table for FIFO job management
- Create Templates table with versioning support
- Create CostTracking table with TTL for 90-day retention
- Enable encryption and point-in-time recovery

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 4: IAM Roles Stack

### Goal

Create 3 consolidated IAM roles (ECSTaskRole, LambdaExecutionRole, AmplifyServiceRole) with appropriate permissions following least privilege for major components (ADR-020).

### Files to Create

- `infrastructure/cloudformation/iam-stack.yaml` - IAM roles template

### Prerequisites

- Task 2 completed (S3 bucket ARN needed)
- Task 3 completed (DynamoDB table ARNs needed)
- Understanding of IAM policy structure and AWS managed policies

### Implementation Steps

1. **Create ECSTaskRole** (for Fargate tasks running generation workers):
   - **Trusted Entity:** `ecs-tasks.amazonaws.com`
   - **Policies:**
     - **Bedrock Access:**
       - Action: `bedrock:InvokeModel`
       - Resource: `arn:aws:bedrock:*::foundation-model/*` (all models)
     - **S3 Access:**
       - Actions: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`
       - Resource: `arn:aws:s3:::${BucketName}/jobs/*` (only jobs prefix)
       - Actions: `s3:GetObject`
       - Resource: `arn:aws:s3:::${BucketName}/seed-data/*`, `arn:aws:s3:::${BucketName}/sample-datasets/*`
     - **DynamoDB Access:**
       - Actions: `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:GetItem`
       - Resources: Jobs table ARN, CostTracking table ARN
     - **CloudWatch Logs:**
       - Actions: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
       - Resource: `arn:aws:logs:*:*:log-group:/aws/ecs/plot-palette-*`

2. **Create LambdaExecutionRole** (for API Lambda functions):
   - **Trusted Entity:** `lambda.amazonaws.com`
   - **Managed Policies:**
     - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
   - **Custom Policies:**
     - **S3 Full Access to Bucket:**
       - Actions: `s3:*`
       - Resource: `arn:aws:s3:::${BucketName}/*` and `arn:aws:s3:::${BucketName}`
     - **DynamoDB Full Access to Tables:**
       - Actions: `dynamodb:*`
       - Resources: All 4 table ARNs
     - **Cognito Read Access:**
       - Actions: `cognito-idp:ListUsers`, `cognito-idp:AdminGetUser`
       - Resource: `*` (will be restricted to User Pool in Phase 2)
     - **STS Assume Role:**
       - Action: `sts:AssumeRole`
       - Resource: `*` (for generating presigned URLs)
     - **ECS Task Management:**
       - Actions: `ecs:RunTask`, `ecs:DescribeTasks`, `ecs:StopTask`
       - Resource: `*` (will be restricted to cluster in Phase 4)

3. **Create AmplifyServiceRole** (for Amplify to deploy frontend):
   - **Trusted Entity:** `amplify.amazonaws.com`
   - **Policies:**
     - **S3 Access:**
       - Actions: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`
       - Resource: Frontend bucket ARN (will be created in Phase 6)
     - **CloudFormation Read:**
       - Actions: `cloudformation:DescribeStacks`, `cloudformation:DescribeStackResources`
       - Resource: `*`

4. **Add Stack Parameters:**
   - `S3BucketName` (from storage stack)
   - `JobsTableArn`, `QueueTableArn`, `TemplatesTableArn`, `CostTrackingTableArn` (from database stack)

5. **Add CloudFormation Outputs:**
   - ECSTaskRole ARN
   - LambdaExecutionRole ARN
   - AmplifyServiceRole ARN

### Verification Checklist

- [ ] All 3 roles created with correct trust policies
- [ ] ECSTaskRole has Bedrock, S3, DynamoDB, CloudWatch permissions
- [ ] LambdaExecutionRole has S3, DynamoDB, Cognito, STS, ECS permissions
- [ ] AmplifyServiceRole has S3 and CloudFormation permissions
- [ ] No overly broad permissions (avoid `*` actions on `*` resources)
- [ ] Roles can be assumed by correct services
- [ ] IAM policy simulator validates expected access

### Testing Instructions

**Unit Test:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/iam-stack.yaml
```

**Integration Test:**
```bash
# First deploy dependencies (storage, database stacks)
# Get their outputs for parameters

BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-storage-test \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text)

JOBS_TABLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-database-test \
  --query 'Stacks[0].Outputs[?OutputKey==`JobsTableArn`].OutputValue' \
  --output text)

# Deploy IAM stack
aws cloudformation create-stack \
  --stack-name plot-palette-iam-test \
  --template-body file://infrastructure/cloudformation/iam-stack.yaml \
  --parameters \
    ParameterKey=S3BucketName,ParameterValue=$BUCKET_NAME \
    ParameterKey=JobsTableArn,ParameterValue=$JOBS_TABLE_ARN \
    ParameterKey=QueueTableArn,ParameterValue=arn:aws:dynamodb:us-east-1:123456789012:table/Queue \
    ParameterKey=TemplatesTableArn,ParameterValue=arn:aws:dynamodb:us-east-1:123456789012:table/Templates \
    ParameterKey=CostTrackingTableArn,ParameterValue=arn:aws:dynamodb:us-east-1:123456789012:table/CostTracking \
  --capabilities CAPABILITY_IAM

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-iam-test

# Get role ARN
TASK_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name plot-palette-iam-test \
  --query 'Stacks[0].Outputs[?OutputKey==`ECSTaskRoleArn`].OutputValue' \
  --output text)

# Test IAM policy simulator
aws iam simulate-principal-policy \
  --policy-source-arn $TASK_ROLE_ARN \
  --action-names bedrock:InvokeModel s3:PutObject dynamodb:PutItem \
  --resource-arns \
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-v2" \
    "arn:aws:s3:::$BUCKET_NAME/jobs/test/output.json" \
    "$JOBS_TABLE_ARN"

# Cleanup
aws cloudformation delete-stack --stack-name plot-palette-iam-test
```

### Commit Message Template

```
feat(infrastructure): add IAM roles for ECS, Lambda, and Amplify

- Create ECSTaskRole with Bedrock, S3, DynamoDB access
- Create LambdaExecutionRole with full backend permissions
- Create AmplifyServiceRole for frontend deployment
- Follow least privilege for major components
- Export role ARNs for other stacks

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~13,000

---

## Task 5: Deployment Script

### Goal

Create a bash script to deploy all Phase 1 CloudFormation stacks in the correct order with proper dependency handling and error checking.

### Files to Create

- `infrastructure/scripts/deploy.sh` - Deployment automation script

### Prerequisites

- Tasks 1-4 completed (all CFN templates created)
- AWS CLI configured
- Bash shell available
- jq installed (for JSON parsing)

### Implementation Steps

1. **Create deployment script structure:**
   - Accept command-line arguments: `--region`, `--profile`, `--environment`
   - Set defaults: region from AWS config, profile default, environment production
   - Validate prerequisites (AWS CLI, jq, templates exist)

2. **Implement stack deployment function:**
   - Function: `deploy_stack(stack_name, template_file, parameters)`
   - Check if stack exists (update vs create)
   - Use `aws cloudformation deploy` for idempotent deployments
   - Wait for stack completion
   - Print outputs after deployment
   - Handle errors and exit on failure

3. **Deploy stacks in dependency order:**
   - Network stack (no dependencies)
   - Storage stack (no dependencies)
   - Database stack (no dependencies)
   - IAM stack (depends on storage and database outputs)

4. **Retrieve and pass outputs between stacks:**
   - Query stack outputs with `aws cloudformation describe-stacks`
   - Pass as parameters to dependent stacks
   - Store all outputs in `outputs.json` for reference

5. **Add cleanup function:**
   - `cleanup()` function to delete all stacks in reverse order
   - Trigger on error or `--delete` flag

6. **Add logging:**
   - Timestamp each action
   - Log to both console and `deployment.log`
   - Color-coded output (green for success, red for errors)

### Verification Checklist

- [ ] Script accepts command-line arguments
- [ ] Validates AWS CLI and jq are installed
- [ ] Deploys stacks in correct order
- [ ] Waits for each stack to complete before proceeding
- [ ] Passes outputs between stacks correctly
- [ ] Handles errors gracefully
- [ ] Creates outputs.json with all stack outputs
- [ ] Cleanup function deletes stacks in reverse order

### Testing Instructions

**Test deployment:**
```bash
# Make script executable
chmod +x infrastructure/scripts/deploy.sh

# Test with dry-run (add --dry-run flag to script)
./infrastructure/scripts/deploy.sh --region us-east-1 --environment dev

# Full deployment
./infrastructure/scripts/deploy.sh --region us-east-1 --environment test

# Verify all stacks created
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# Check outputs.json
cat infrastructure/scripts/outputs.json

# Test cleanup
./infrastructure/scripts/deploy.sh --delete --environment test
```

**Script should produce output like:**
```
[2025-11-19 10:00:00] Starting deployment to us-east-1...
[2025-11-19 10:00:05] Deploying network stack...
[2025-11-19 10:02:30] ✓ Network stack deployed
[2025-11-19 10:02:35] Deploying storage stack...
[2025-11-19 10:04:00] ✓ Storage stack deployed
...
[2025-11-19 10:15:00] ✓ All stacks deployed successfully
[2025-11-19 10:15:01] Outputs saved to outputs.json
```

### Commit Message Template

```
feat(infrastructure): add deployment script for CloudFormation stacks

- Create bash script to deploy all infrastructure stacks
- Handle dependencies and output passing between stacks
- Add error handling and rollback capability
- Generate outputs.json with all stack outputs
- Support multiple environments (dev, test, production)

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~10,000

---

## Task 6: Backend Shared Library

### Goal

Create shared Python modules for constants, data models, and utility functions that will be used across Lambda functions and ECS tasks.

### Files to Create

- `backend/shared/__init__.py` - Package initialization
- `backend/shared/models.py` - Pydantic models for type safety
- `backend/shared/constants.py` - Application constants
- `backend/shared/utils.py` - Utility functions
- `backend/requirements.txt` - Python dependencies

### Prerequisites

- Python 3.13 installed
- Understanding of Pydantic for data validation
- Reviewed ADR-005 (DynamoDB schemas) and ADR-009 (Python runtime)

### Implementation Steps

1. **Create `constants.py`** with application-wide constants:
   - Job statuses: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `BUDGET_EXCEEDED`, `CANCELLED`
   - Export formats: `JSONL`, `PARQUET`, `CSV`
   - Model pricing (per 1M tokens):
     - Claude Sonnet: input $3.00, output $15.00
     - Llama 3.1 70B: input $0.99, output $0.99
     - Llama 3.1 8B: input $0.30, output $0.60
     - Mistral 7B: input $0.15, output $0.20
   - Fargate pricing (Spot):
     - vCPU: $0.01246 per hour
     - Memory: $0.00127 per GB per hour
   - S3 pricing:
     - PUT: $0.005 per 1000 requests
     - GET: $0.0004 per 1000 requests
   - Checkpoint interval: 50 records
   - Budget check interval: every Bedrock call

2. **Create `models.py`** with Pydantic models:
   - `JobConfig` model matching DynamoDB Jobs table schema
   - `TemplateDefinition` model for prompt templates
   - `CheckpointState` model for checkpoint JSON
   - `CostBreakdown` model for cost tracking
   - Use Pydantic for validation, serialization to DynamoDB format

   **Example structure:**
   ```python
   from pydantic import BaseModel, Field
   from typing import Optional, Dict, List
   from datetime import datetime
   from enum import Enum

   class JobStatus(str, Enum):
       QUEUED = "QUEUED"
       RUNNING = "RUNNING"
       COMPLETED = "COMPLETED"
       FAILED = "FAILED"
       BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
       CANCELLED = "CANCELLED"

   class JobConfig(BaseModel):
       job_id: str
       user_id: str
       status: JobStatus
       created_at: datetime
       updated_at: datetime
       config: Dict
       budget_limit: float
       tokens_used: int = 0
       records_generated: int = 0
       cost_estimate: float = 0.0

       def to_dynamodb(self) -> dict:
           # Convert to DynamoDB format
           pass
   ```

3. **Create `utils.py`** with utility functions:
   - `generate_job_id()` - Create UUID for jobs
   - `calculate_cost(tokens, model_id)` - Calculate Bedrock cost
   - `get_nested_field(data, field_path)` - Get nested dict value (e.g., "author.biography")
   - `create_presigned_url(bucket, key, expiration)` - Generate S3 presigned URLs
   - `parse_etag(etag)` - Clean ETag strings (remove quotes)
   - `setup_logger(name)` - Configure structured JSON logging
   - Include error handling and type hints

4. **Create `requirements.txt`:**
   ```
   boto3>=1.34.0
   pydantic>=2.5.0
   requests>=2.31.0
   python-dotenv>=1.0.0
   jinja2>=3.1.2
   pyarrow>=14.0.0
   pandas>=2.1.0
   jsonschema>=4.20.0
   ```

5. **Add `__init__.py`** to make it a package and expose main classes:
   ```python
   from .models import JobConfig, TemplateDefinition, CheckpointState
   from .constants import JobStatus, ExportFormat, MODEL_PRICING
   from .utils import generate_job_id, calculate_cost, setup_logger

   __all__ = [
       "JobConfig", "TemplateDefinition", "CheckpointState",
       "JobStatus", "ExportFormat", "MODEL_PRICING",
       "generate_job_id", "calculate_cost", "setup_logger"
   ]
   ```

6. **Follow coding standards:**
   - Type hints on all functions
   - Docstrings (Google style)
   - Black formatting (line length 100)
   - No hardcoded values (use constants)

### Verification Checklist

- [ ] All files created with correct structure
- [ ] Pydantic models match DynamoDB schemas
- [ ] Constants include all pricing and configuration values
- [ ] Utility functions have type hints and docstrings
- [ ] requirements.txt includes all dependencies
- [ ] Package imports work correctly (`from backend.shared import JobConfig`)
- [ ] Black formatting applied
- [ ] No syntax errors

### Testing Instructions

**Unit Tests (create `tests/unit/test_shared.py`):**
```python
import pytest
from backend.shared.models import JobConfig, JobStatus
from backend.shared.utils import generate_job_id, calculate_cost
from backend.shared.constants import MODEL_PRICING

def test_job_config_creation():
    job = JobConfig(
        job_id="test-123",
        user_id="user-456",
        status=JobStatus.QUEUED,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        config={},
        budget_limit=100.0
    )
    assert job.status == JobStatus.QUEUED
    assert job.tokens_used == 0

def test_generate_job_id():
    job_id = generate_job_id()
    assert len(job_id) == 36  # UUID format
    assert "-" in job_id

def test_calculate_cost():
    cost = calculate_cost(tokens=1000000, model_id="claude-sonnet")
    assert cost > 0
    # Verify against MODEL_PRICING constants

# Run tests
# pytest tests/unit/test_shared.py -v
```

**Manual Test (Python REPL):**
```bash
python3.13
>>> from backend.shared import JobConfig, JobStatus, generate_job_id
>>> job_id = generate_job_id()
>>> print(job_id)
>>> job = JobConfig(...)
>>> print(job.to_dynamodb())
```

### Commit Message Template

```
feat(backend): add shared library for models, constants, and utils

- Create Pydantic models for Jobs, Templates, Checkpoints
- Add constants for pricing, statuses, and configuration
- Implement utility functions for ID generation, cost calculation, logging
- Define requirements.txt with all Python dependencies
- Follow type hints and docstring standards

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 7: Update Repository README

### Goal

Update the main README.md to reflect the new AWS-based architecture and provide setup instructions for the transformed system.

### Files to Modify

- `README.md` - Root repository README

### Prerequisites

- All Phase 1 tasks completed
- Understanding of new architecture (Phase 0)

### Implementation Steps

1. **Update project description** at the top:
   - Explain transformation from systemd to AWS serverless
   - Highlight key features: Fargate Spot, Bedrock, web UI, multi-format export
   - Update badges if applicable

2. **Add architecture diagram** (ASCII or link to image):
   - Show flow: User → Amplify UI → API Gateway → Lambda → ECS Fargate Spot → Bedrock
   - Include S3 and DynamoDB in diagram

3. **Update installation section:**
   - Prerequisites: AWS account, CLI, Python 3.13, Node.js 20+
   - Quick start: Run deployment script
   - Link to detailed setup guide (will be created in Phase 9)

4. **Add deployment instructions:**
   ```bash
   # Clone repository
   git clone https://github.com/HatmanStack/plot-palette.git
   cd plot-palette

   # Deploy infrastructure
   ./infrastructure/scripts/deploy.sh --region us-east-1 --environment production

   # Access web UI
   # URL will be output by deployment script
   ```

5. **Update features section:**
   - Web-based UI for job management
   - Real-time progress tracking and cost monitoring
   - Custom prompt templates with multi-step generation
   - Multiple export formats (JSONL, Parquet, CSV)
   - Automatic Glacier archival
   - Budget limits and cost controls

6. **Add architecture section:**
   - List AWS services used
   - Explain Fargate Spot cost savings
   - Mention Bedrock model selection

7. **Update license and attribution:**
   - Keep existing license
   - Update model list if using different Bedrock models
   - Acknowledge AWS services

8. **Add "Migration from v1" section:**
   - Note for existing users about breaking changes
   - Explain how to migrate seed data to S3
   - Offer support channel (GitHub issues)

### Verification Checklist

- [ ] README accurately describes new architecture
- [ ] Installation instructions are clear and complete
- [ ] All links work (documentation, HuggingFace dataset, etc.)
- [ ] Markdown formatting is correct
- [ ] Badges updated (if applicable)
- [ ] License section preserved

### Testing Instructions

**Manual Review:**
- Render README in GitHub or with `grip` tool
- Follow installation instructions on a fresh AWS account (or document steps)
- Verify all links are valid
- Check for typos and grammar

**Automated Check:**
```bash
# Install markdown linter
npm install -g markdownlint-cli

# Lint README
markdownlint README.md

# Check links (requires markdown-link-check)
npm install -g markdown-link-check
markdown-link-check README.md
```

### Commit Message Template

```
docs: update README for AWS serverless architecture

- Rewrite project description for AWS deployment
- Add architecture diagram and service overview
- Update installation instructions with deployment script
- Document new features (web UI, cost tracking, templates)
- Add migration guide for v1 users
- Preserve license and attribution

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~8,000

---

## Phase 1 Verification

After completing all tasks, verify the entire phase:

### Integration Tests

1. **Deploy all stacks:**
   ```bash
   ./infrastructure/scripts/deploy.sh --region us-east-1 --environment test
   ```

2. **Verify VPC:**
   ```bash
   aws ec2 describe-vpcs --filters "Name=tag:Name,Values=plot-palette-*"
   aws ec2 describe-subnets --filters "Name=vpc-id,Values=<vpc-id>"
   ```

3. **Verify S3:**
   ```bash
   aws s3 ls
   aws s3api get-bucket-lifecycle-configuration --bucket <bucket-name>
   ```

4. **Verify DynamoDB:**
   ```bash
   aws dynamodb list-tables
   aws dynamodb describe-table --table-name plot-palette-Jobs
   ```

5. **Verify IAM:**
   ```bash
   aws iam get-role --role-name plot-palette-ECSTaskRole
   aws iam get-role-policy --role-name plot-palette-ECSTaskRole --policy-name BedrockAccess
   ```

6. **Test shared library:**
   ```bash
   cd backend
   python3.13 -m pytest tests/unit/test_shared.py -v
   ```

### Success Criteria

- [ ] All CloudFormation stacks deployed successfully
- [ ] VPC has 3 public subnets in different AZs
- [ ] S3 bucket created with lifecycle policies
- [ ] 4 DynamoDB tables exist with correct schemas
- [ ] 3 IAM roles created with appropriate permissions
- [ ] Deployment script runs without errors
- [ ] Shared library passes all unit tests
- [ ] README accurately describes the system
- [ ] No hardcoded values in code (use constants)
- [ ] All resources tagged appropriately

### Estimated Total Cost (Phase 1 deployed for 1 hour)

- VPC, subnets, IGW: $0
- S3 bucket (empty): $0
- DynamoDB (on-demand, no data): $0
- IAM roles: $0
- **Total: $0** (all resources are free when idle)

---

## Known Limitations & Technical Debt

1. **No VPC Endpoints:** Using public internet for AWS API calls (acceptable for now, can add VPC endpoints later for optimization)
2. **Single Region Template:** While templates are region-agnostic, no cross-region replication yet
3. **No CloudWatch Alarms:** Monitoring configured in later phases
4. **IAM Policies Not Fully Restricted:** Some resources use `*`, will tighten in Phase 7 during CFN integration

---

## Next Steps

With core infrastructure deployed, you're ready to proceed to **Phase 2: Authentication & API Gateway**.

Phase 2 will add:
- Cognito User Pool for authentication
- HTTP API Gateway with JWT authorizer
- Lambda functions for basic API operations (health check, user info)

---

**Navigation:**
- [← Back to README](./README.md)
- [← Previous: Phase 0](./Phase-0.md)
- [Next: Phase 2 - Authentication & API Gateway →](./Phase-2.md)
