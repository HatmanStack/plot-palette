# Phase 3: Backend APIs & Job Management

## Phase Goal

Build the complete backend API layer for managing generation jobs, prompt templates, seed data uploads, and real-time progress tracking. By the end of this phase, users can create jobs, upload seed data, manage templates, and query job status through API endpoints - all the functionality needed for the frontend in Phase 6.

**Success Criteria:**
- Lambda functions for all core API operations (jobs, templates, seed data, dashboard)
- DynamoDB integration for storing and querying job/template data
- S3 presigned URL generation for seed data uploads
- Real-time cost calculation and budget tracking
- Job queue management (QUEUED → RUNNING transitions)
- All endpoints tested with automated integration tests

**Estimated Tokens:** ~102,000

---

## Prerequisites

- **Phase 1** completed (Infrastructure deployed)
- **Phase 2** completed (Authentication working, API Gateway deployed)
- Cognito User Pool with test users
- API Gateway endpoint accessible
- DynamoDB tables created (Jobs, Queue, Templates, CostTracking)
- S3 bucket available for seed data storage

---

## Task 1: Lambda Function - Create Job

### Goal

Implement POST /jobs endpoint to create new generation jobs with configuration validation, budget limits, and queue insertion.

### Files to Create

- `backend/lambdas/jobs/create_job.py` - Create job Lambda handler
- `backend/lambdas/jobs/requirements.txt` - Dependencies
- `backend/lambdas/jobs/__init__.py` - Package initialization

### Prerequisites

- Phase 1 Task 6 (shared library with JobConfig model)
- Understanding of DynamoDB conditional writes
- Knowledge of job configuration schema

### Implementation Steps

1. **Create handler function structure:**
   - Extract user_id from JWT claims (`event['requestContext']['authorizer']['jwt']['claims']['sub']`)
   - Parse request body (job configuration JSON)
   - Validate configuration fields
   - Generate job ID
   - Insert job record into DynamoDB Jobs table
   - Insert into Queue table with QUEUED status
   - Return job ID and creation confirmation

2. **Job configuration validation:**
   - Required fields: `template_id`, `seed_data_path`, `budget_limit`, `output_format`, `num_records`
   - Optional fields: `task_size` (vCPU/memory), `partition_strategy`, `export_config`
   - Validate budget_limit > 0 and <= 1000 (reasonable limit)
   - Validate output_format in [JSONL, PARQUET, CSV]
   - Validate num_records > 0 and <= 1000000
   - Validate template_id exists in Templates table

3. **Handler implementation pattern:**
   ```python
   import json
   import boto3
   from datetime import datetime
   from backend.shared.models import JobConfig, JobStatus
   from backend.shared.utils import generate_job_id, setup_logger
   from backend.shared.constants import ExportFormat

   logger = setup_logger(__name__)
   dynamodb = boto3.resource('dynamodb')
   jobs_table = dynamodb.Table('plot-palette-Jobs')
   queue_table = dynamodb.Table('plot-palette-Queue')
   templates_table = dynamodb.Table('plot-palette-Templates')

   def lambda_handler(event, context):
       try:
           # Extract user from JWT
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

           # Parse request body
           body = json.loads(event['body'])

           # Validate template exists
           template = templates_table.get_item(
               Key={'template_id': body['template_id'], 'version': body.get('template_version', 1)}
           )
           if 'Item' not in template:
               return error_response(404, "Template not found")

           # Create job record
           job_id = generate_job_id()
           now = datetime.utcnow().isoformat()

           job = JobConfig(
               job_id=job_id,
               user_id=user_id,
               status=JobStatus.QUEUED,
               created_at=now,
               updated_at=now,
               config=body,
               budget_limit=body['budget_limit'],
               tokens_used=0,
               records_generated=0,
               cost_estimate=0.0
           )

           # Insert into Jobs table
           jobs_table.put_item(Item=job.to_dynamodb())

           # Insert into Queue table
           queue_table.put_item(Item={
               'status': 'QUEUED',
               'job_id#timestamp': f"{job_id}#{now}",
               'job_id': job_id,
               'priority': body.get('priority', 5)
           })

           logger.info(json.dumps({
               "event": "job_created",
               "job_id": job_id,
               "user_id": user_id
           }))

           return {
               "statusCode": 201,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "job_id": job_id,
                   "status": "QUEUED",
                   "created_at": now
               })
           }

       except ValueError as e:
           logger.error(f"Validation error: {str(e)}")
           return error_response(400, str(e))
       except Exception as e:
           logger.error(f"Error creating job: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")

   def error_response(status_code, message):
       return {
           "statusCode": status_code,
           "headers": {"Content-Type": "application/json"},
           "body": json.dumps({"error": message})
       }
   ```

4. **Update API Gateway stack:**
   - Add POST /jobs route
   - Attach JWT authorizer
   - Create Lambda integration
   - Add Lambda permission

5. **Add requirements.txt:**
   ```
   boto3>=1.34.0
   ../shared
   ```

### Verification Checklist

- [ ] Handler validates all required fields
- [ ] Template existence validated before job creation
- [ ] Job ID generated and returned
- [ ] Job inserted into Jobs table
- [ ] Job inserted into Queue table with QUEUED status
- [ ] User ID from JWT correctly extracted
- [ ] Returns 400 for invalid config
- [ ] Returns 404 for non-existent template
- [ ] Returns 500 for unexpected errors
- [ ] Structured logging implemented

### Testing Instructions

**Unit Test (create `tests/unit/test_create_job.py`):**
```python
import json
import pytest
from unittest.mock import Mock, patch
from backend.lambdas.jobs.create_job import lambda_handler

@patch('backend.lambdas.jobs.create_job.jobs_table')
@patch('backend.lambdas.jobs.create_job.queue_table')
@patch('backend.lambdas.jobs.create_job.templates_table')
def test_create_job_success(mock_templates, mock_queue, mock_jobs):
    # Mock template exists
    mock_templates.get_item.return_value = {'Item': {'template_id': 'tpl-123'}}

    event = {
        'requestContext': {
            'authorizer': {'jwt': {'claims': {'sub': 'user-456'}}}
        },
        'body': json.dumps({
            'template_id': 'tpl-123',
            'seed_data_path': 's3://bucket/seed/',
            'budget_limit': 100.0,
            'output_format': 'JSONL',
            'num_records': 1000
        })
    }

    response = lambda_handler(event, Mock())

    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert 'job_id' in body
    assert body['status'] == 'QUEUED'

    mock_jobs.put_item.assert_called_once()
    mock_queue.put_item.assert_called_once()

def test_create_job_template_not_found(mock_templates, mock_queue, mock_jobs):
    mock_templates.get_item.return_value = {}

    event = {
        'requestContext': {
            'authorizer': {'jwt': {'claims': {'sub': 'user-456'}}}
        },
        'body': json.dumps({'template_id': 'invalid', 'budget_limit': 100})
    }

    response = lambda_handler(event, Mock())

    assert response['statusCode'] == 404

# Run: pytest tests/unit/test_create_job.py -v
```

**Integration Test:**
```bash
# Get auth token
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id $CLIENT_ID \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123! \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# Create test template first (will be implemented in Task 4)

# Create job
curl -X POST $API_ENDPOINT/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "tpl-123",
    "seed_data_path": "seed-data/test/",
    "budget_limit": 50.0,
    "output_format": "JSONL",
    "num_records": 100
  }'

# Expected: 201 with job_id in response
```

### Commit Message Template

```
feat(jobs): add create job API endpoint

- Implement POST /jobs Lambda handler
- Validate job configuration and budget limits
- Insert job into DynamoDB Jobs and Queue tables
- Verify template exists before creating job
- Extract user ID from JWT claims
- Add comprehensive error handling and validation

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~16,000

---

## Task 2: Lambda Function - List and Get Jobs

### Goal

Implement GET /jobs (list user's jobs) and GET /jobs/{job_id} (get single job details) endpoints.

### Files to Create

- `backend/lambdas/jobs/list_jobs.py` - List jobs handler
- `backend/lambdas/jobs/get_job.py` - Get single job handler

### Prerequisites

- Task 1 completed (jobs table has data)
- Understanding of DynamoDB GSI queries

### Implementation Steps

1. **Create list_jobs handler:**
   - Query Jobs table using user-id-index GSI
   - Extract user_id from JWT claims
   - Support pagination with `limit` and `last_evaluated_key` query parameters
   - Support filtering by status (query parameter: `?status=RUNNING`)
   - Return sorted by created_at (descending - newest first)
   - Include summary data (not full config)

2. **List jobs implementation:**
   ```python
   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']

           # Parse query parameters
           params = event.get('queryStringParameters') or {}
           limit = int(params.get('limit', 20))
           status_filter = params.get('status')

           query_params = {
               'IndexName': 'user-id-index',
               'KeyConditionExpression': 'user_id = :uid',
               'ExpressionAttributeValues': {':uid': user_id},
               'Limit': limit,
               'ScanIndexForward': False  # Descending order
           }

           # Add status filter if provided
           if status_filter:
               query_params['FilterExpression'] = 'status = :status'
               query_params['ExpressionAttributeValues'][':status'] = status_filter

           # Handle pagination
           if 'last_key' in params:
               query_params['ExclusiveStartKey'] = json.loads(params['last_key'])

           response = jobs_table.query(**query_params)

           jobs = [{
               'job_id': item['job_id'],
               'status': item['status'],
               'created_at': item['created_at'],
               'updated_at': item['updated_at'],
               'records_generated': item.get('records_generated', 0),
               'cost_estimate': item.get('cost_estimate', 0.0),
               'budget_limit': item['budget_limit']
           } for item in response['Items']]

           result = {'jobs': jobs}
           if 'LastEvaluatedKey' in response:
               result['last_key'] = json.dumps(response['LastEvaluatedKey'])

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps(result)
           }

       except Exception as e:
           logger.error(f"Error listing jobs: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Create get_job handler:**
   - Extract job_id from path parameter: `event['pathParameters']['job_id']`
   - Get item from Jobs table
   - Verify user_id matches (authorization check)
   - Return full job details including config
   - Return 404 if job not found
   - Return 403 if user doesn't own job

4. **Get job implementation:**
   ```python
   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           job_id = event['pathParameters']['job_id']

           # Get job from DynamoDB
           response = jobs_table.get_item(Key={'job_id': job_id})

           if 'Item' not in response:
               return error_response(404, "Job not found")

           job = response['Item']

           # Authorization check
           if job['user_id'] != user_id:
               return error_response(403, "Access denied")

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps(job, default=str)  # Handle datetime serialization
           }

       except Exception as e:
           logger.error(f"Error getting job: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

5. **Update API Gateway stack:**
   - Add GET /jobs route → list_jobs Lambda
   - Add GET /jobs/{job_id} route → get_job Lambda
   - Both require JWT authorizer

### Verification Checklist

- [ ] List jobs queries correct GSI
- [ ] List jobs filters by user_id
- [ ] Pagination works with limit and last_key
- [ ] Status filter works correctly
- [ ] Jobs sorted by created_at descending
- [ ] Get job returns full job details
- [ ] Get job returns 404 if not found
- [ ] Get job returns 403 if wrong user
- [ ] Both endpoints handle errors gracefully

### Testing Instructions

**Integration Test:**
```bash
# List jobs
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/jobs

# List with pagination
curl -H "Authorization: Bearer $TOKEN" "$API_ENDPOINT/jobs?limit=10"

# Filter by status
curl -H "Authorization: Bearer $TOKEN" "$API_ENDPOINT/jobs?status=RUNNING"

# Get specific job
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/jobs/$JOB_ID

# Try to access another user's job (should return 403)
curl -H "Authorization: Bearer $OTHER_USER_TOKEN" $API_ENDPOINT/jobs/$JOB_ID
```

### Commit Message Template

```
feat(jobs): add list and get job endpoints

- Implement GET /jobs to list user's jobs with pagination
- Implement GET /jobs/{id} to get single job details
- Query DynamoDB GSI for user's jobs sorted by date
- Support status filtering and pagination
- Add authorization check to prevent cross-user access
- Return 403 if user tries to access another user's job

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Task 3: Lambda Function - Cancel/Delete Job

### Goal

Implement DELETE /jobs/{job_id} endpoint to cancel running jobs or delete completed jobs.

### Files to Create

- `backend/lambdas/jobs/delete_job.py` - Delete job handler

### Prerequisites

- Tasks 1-2 completed (job creation and retrieval)
- Understanding of DynamoDB conditional updates

### Implementation Steps

1. **Create delete handler with state-aware logic:**
   - If job status is QUEUED: remove from queue, update status to CANCELLED
   - If job status is RUNNING: signal ECS task to stop, update status to CANCELLED
   - If job status is COMPLETED/FAILED/CANCELLED: delete job record and S3 data
   - Verify user owns job (authorization)

2. **Handler implementation:**
   ```python
   import boto3

   ecs_client = boto3.client('ecs')
   s3_client = boto3.client('s3')

   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           job_id = event['pathParameters']['job_id']

           # Get current job
           response = jobs_table.get_item(Key={'job_id': job_id})
           if 'Item' not in response:
               return error_response(404, "Job not found")

           job = response['Item']
           if job['user_id'] != user_id:
               return error_response(403, "Access denied")

           status = job['status']

           if status == 'QUEUED':
               # Remove from queue
               queue_table.delete_item(
                   Key={
                       'status': 'QUEUED',
                       'job_id#timestamp': f"{job_id}#{job['created_at']}"
                   }
               )
               # Update job status
               jobs_table.update_item(
                   Key={'job_id': job_id},
                   UpdateExpression='SET #status = :status, updated_at = :now',
                   ExpressionAttributeNames={'#status': 'status'},
                   ExpressionAttributeValues={
                       ':status': 'CANCELLED',
                       ':now': datetime.utcnow().isoformat()
                   }
               )
               message = "Job cancelled"

           elif status == 'RUNNING':
               # Stop ECS task
               task_arn = job.get('task_arn')
               if task_arn:
                   ecs_client.stop_task(
                       cluster='plot-palette-cluster',
                       task=task_arn,
                       reason='User cancelled job'
                   )
               # Update status
               jobs_table.update_item(
                   Key={'job_id': job_id},
                   UpdateExpression='SET #status = :status, updated_at = :now',
                   ExpressionAttributeNames={'#status': 'status'},
                   ExpressionAttributeValues={
                       ':status': 'CANCELLED',
                       ':now': datetime.utcnow().isoformat()
                   }
               )
               message = "Job cancellation requested"

           else:  # COMPLETED, FAILED, CANCELLED, BUDGET_EXCEEDED
               # Delete S3 data
               bucket = os.environ['BUCKET_NAME']
               prefix = f"jobs/{job_id}/"
               paginator = s3_client.get_paginator('list_objects_v2')
               for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                   if 'Contents' in page:
                       objects = [{'Key': obj['Key']} for obj in page['Contents']]
                       s3_client.delete_objects(
                           Bucket=bucket,
                           Delete={'Objects': objects}
                       )

               # Delete job record
               jobs_table.delete_item(Key={'job_id': job_id})

               # Delete cost tracking records
               cost_response = cost_tracking_table.query(
                   KeyConditionExpression='job_id = :jid',
                   ExpressionAttributeValues={':jid': job_id}
               )
               for item in cost_response.get('Items', []):
                   cost_tracking_table.delete_item(
                       Key={'job_id': job_id, 'timestamp': item['timestamp']}
                   )

               message = "Job deleted"

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({"message": message, "job_id": job_id})
           }

       except Exception as e:
           logger.error(f"Error deleting job: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Add environment variables:**
   - BUCKET_NAME (S3 bucket from Phase 1)
   - ECS_CLUSTER_NAME (will be created in Phase 4)

4. **Update IAM role:**
   - Add ECS StopTask permission to LambdaExecutionRole
   - Add S3 DeleteObject permission

5. **Update API Gateway:**
   - Add DELETE /jobs/{job_id} route
   - Attach JWT authorizer

### Verification Checklist

- [ ] Cancels QUEUED jobs (removes from queue)
- [ ] Stops RUNNING jobs (signals ECS task)
- [ ] Deletes completed jobs and S3 data
- [ ] Deletes cost tracking records
- [ ] Returns 403 if user doesn't own job
- [ ] Returns 404 if job not found
- [ ] Handles S3 pagination for large datasets
- [ ] Logs actions for audit trail

### Testing Instructions

**Integration Test:**
```bash
# Create a test job
JOB_ID=$(curl -X POST $API_ENDPOINT/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template_id":"tpl-123","budget_limit":50,"num_records":100}' \
  | jq -r '.job_id')

# Delete job while QUEUED
curl -X DELETE $API_ENDPOINT/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"

# Verify job status is CANCELLED
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/jobs/$JOB_ID

# Delete again (should fully delete)
curl -X DELETE $API_ENDPOINT/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"

# Verify job no longer exists (404)
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/jobs/$JOB_ID
```

### Commit Message Template

```
feat(jobs): add delete/cancel job endpoint

- Implement DELETE /jobs/{id} with state-aware logic
- Cancel QUEUED jobs by removing from queue
- Stop RUNNING jobs by signaling ECS tasks
- Delete completed jobs including S3 data and cost records
- Add S3 pagination for deleting large datasets
- Update IAM role with ECS StopTask and S3 DeleteObject permissions

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 4: Lambda Functions - Template CRUD

### Goal

Implement full CRUD operations for prompt templates: create, list, get, update, delete.

### Files to Create

- `backend/lambdas/templates/create_template.py`
- `backend/lambdas/templates/list_templates.py`
- `backend/lambdas/templates/get_template.py`
- `backend/lambdas/templates/update_template.py`
- `backend/lambdas/templates/delete_template.py`
- `backend/lambdas/templates/requirements.txt`

### Prerequisites

- Understanding of template structure from ADR-016
- Jinja2 template parsing for schema extraction
- DynamoDB versioning pattern (partition key + sort key for versions)

### Implementation Steps

1. **Create POST /templates handler:**
   - Parse template definition from request body
   - Validate Jinja2 syntax (parse template, catch errors)
   - Extract required fields (schema_requirements) from template
   - Generate template_id
   - Insert with version = 1
   - Return template_id

2. **Create template handler:**
   ```python
   import jinja2
   import jinja2.meta

   def extract_schema_requirements(template_str):
       """Extract all {{ variable }} references from Jinja2 template"""
       env = jinja2.Environment()
       try:
           ast = env.parse(template_str)
           variables = jinja2.meta.find_undeclared_variables(ast)
           return sorted(list(variables))
       except jinja2.TemplateSyntaxError as e:
           raise ValueError(f"Invalid template syntax: {str(e)}")

   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           body = json.loads(event['body'])

           # Validate required fields
           if 'name' not in body or 'template_definition' not in body:
               return error_response(400, "Missing required fields")

           # Validate template syntax
           template_def = body['template_definition']
           try:
               schema_reqs = extract_schema_requirements(
                   json.dumps(template_def)  # Convert dict to string for parsing
               )
           except ValueError as e:
               return error_response(400, str(e))

           # Create template record
           template_id = generate_template_id()
           now = datetime.utcnow().isoformat()

           template = {
               'template_id': template_id,
               'version': 1,
               'name': body['name'],
               'user_id': user_id,
               'template_definition': template_def,
               'schema_requirements': schema_reqs,
               'created_at': now,
               'is_public': body.get('is_public', False)
           }

           templates_table.put_item(Item=template)

           return {
               "statusCode": 201,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "template_id": template_id,
                   "version": 1,
                   "schema_requirements": schema_reqs
               })
           }

       except Exception as e:
           logger.error(f"Error creating template: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Create GET /templates handler (list):**
   - Query Templates table by user-id-index
   - Return latest version of each template
   - Support filtering by is_public (show public templates from all users)

4. **Create GET /templates/{template_id} handler:**
   - Get specific version (query param: `?version=2`) or latest
   - Return full template definition
   - Check user ownership unless template is public

5. **Create PUT /templates/{template_id} handler:**
   - Increment version number
   - Validate new template syntax
   - Extract schema requirements
   - Insert new version (don't update existing - immutability)

6. **Create DELETE /templates/{template_id} handler:**
   - Check if template is used by any jobs (query Jobs table)
   - If used, return 409 Conflict
   - Otherwise, delete all versions

7. **Update API Gateway:**
   - POST /templates
   - GET /templates
   - GET /templates/{id}
   - PUT /templates/{id}
   - DELETE /templates/{id}

### Verification Checklist

- [ ] Creates template with version 1
- [ ] Validates Jinja2 syntax on creation
- [ ] Extracts schema requirements automatically
- [ ] Lists user's templates (latest version only)
- [ ] Shows public templates from all users
- [ ] Gets specific template version
- [ ] Updates template by creating new version
- [ ] Prevents deletion of templates in use
- [ ] All operations check user ownership (except public templates)

### Testing Instructions

**Integration Test:**
```bash
# Create template
TEMPLATE_ID=$(curl -X POST $API_ENDPOINT/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Template",
    "template_definition": {
      "steps": [{
        "id": "question",
        "model": "llama-3.1-8b",
        "prompt": "Generate a question about {{ author.name }}"
      }]
    }
  }' | jq -r '.template_id')

# List templates
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/templates

# Get template
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/templates/$TEMPLATE_ID

# Update template (creates version 2)
curl -X PUT $API_ENDPOINT/templates/$TEMPLATE_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Template", "template_definition": {...}}'

# Get specific version
curl -H "Authorization: Bearer $TOKEN" "$API_ENDPOINT/templates/$TEMPLATE_ID?version=1"

# Try to delete (should fail if used by jobs)
curl -X DELETE $API_ENDPOINT/templates/$TEMPLATE_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Commit Message Template

```
feat(templates): add full CRUD operations for prompt templates

- Implement POST /templates with Jinja2 validation
- Auto-extract schema requirements from template variables
- Implement GET /templates with user/public filtering
- Implement GET /templates/{id} with version support
- Implement PUT /templates/{id} with versioning (immutable updates)
- Implement DELETE /templates/{id} with usage validation
- Prevent deletion of templates referenced by jobs

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~18,000

---

## Task 5: Lambda Function - Seed Data Upload (Presigned URLs)

### Goal

Implement POST /seed-data/upload endpoint that generates presigned S3 URLs for uploading seed data files, and POST /seed-data/validate to validate uploaded data against template schema.

### Files to Create

- `backend/lambdas/seed_data/generate_upload_url.py`
- `backend/lambdas/seed_data/validate_seed_data.py`
- `backend/lambdas/seed_data/requirements.txt`

### Prerequisites

- Understanding of S3 presigned URLs
- Knowledge of template schema validation (ADR-017)
- jsonschema library for validation

### Implementation Steps

1. **Create generate_upload_url handler:**
   - Accept filename and content_type in request body
   - Generate S3 key: `seed-data/{user_id}/{filename}`
   - Create presigned PUT URL (expires in 15 minutes)
   - Return presigned URL and S3 key

2. **Generate URL implementation:**
   ```python
   import boto3
   from botocore.config import Config

   s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           body = json.loads(event['body'])

           filename = body.get('filename')
           content_type = body.get('content_type', 'application/json')

           if not filename:
               return error_response(400, "filename is required")

           # Generate S3 key
           s3_key = f"seed-data/{user_id}/{filename}"
           bucket = os.environ['BUCKET_NAME']

           # Generate presigned URL
           presigned_url = s3_client.generate_presigned_url(
               'put_object',
               Params={
                   'Bucket': bucket,
                   'Key': s3_key,
                   'ContentType': content_type
               },
               ExpiresIn=900  # 15 minutes
           )

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "upload_url": presigned_url,
                   "s3_key": s3_key,
                   "expires_in": 900
               })
           }

       except Exception as e:
           logger.error(f"Error generating upload URL: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Create validate_seed_data handler:**
   - Accept s3_key and template_id in request body
   - Get template from DynamoDB
   - Download seed data file from S3 (stream, don't load all in memory)
   - Check if seed data has all fields required by template schema
   - Return validation result (valid/invalid with missing fields)

4. **Validate seed data implementation:**
   ```python
   def get_nested_field(data, field_path):
       """Get nested field value, e.g., 'author.biography' from {'author': {'biography': '...'}}"""
       keys = field_path.split('.')
       value = data
       for key in keys:
           if isinstance(value, dict) and key in value:
               value = value[key]
           else:
               return None
       return value

   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           body = json.loads(event['body'])

           s3_key = body.get('s3_key')
           template_id = body.get('template_id')

           # Get template
           template = templates_table.get_item(
               Key={'template_id': template_id, 'version': 1}  # Or get latest version
           )
           if 'Item' not in template:
               return error_response(404, "Template not found")

           schema_reqs = template['Item']['schema_requirements']

           # Download seed data sample (first 1MB to avoid memory issues)
           bucket = os.environ['BUCKET_NAME']
           response = s3_client.get_object(Bucket=bucket, Key=s3_key, Range='bytes=0-1048576')
           data_sample = json.loads(response['Body'].read())

           # Validate schema
           missing_fields = []
           for field in schema_reqs:
               if get_nested_field(data_sample, field) is None:
                   missing_fields.append(field)

           if missing_fields:
               return {
                   "statusCode": 400,
                   "headers": {"Content-Type": "application/json"},
                   "body": json.dumps({
                       "valid": False,
                       "missing_fields": missing_fields
                   })
               }

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps({
                   "valid": True,
                   "message": "Seed data is valid for template"
               })
           }

       except json.JSONDecodeError:
           return error_response(400, "Invalid JSON in seed data file")
       except Exception as e:
           logger.error(f"Error validating seed data: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

5. **Update API Gateway:**
   - POST /seed-data/upload → generate_upload_url
   - POST /seed-data/validate → validate_seed_data

6. **Add requirements.txt:**
   ```
   boto3>=1.34.0
   jsonschema>=4.20.0
   ../shared
   ```

### Verification Checklist

- [ ] Generates presigned URL with correct expiration
- [ ] S3 key includes user_id for isolation
- [ ] Presigned URL works for uploading files
- [ ] Validation downloads only sample of large files
- [ ] Validation checks all schema requirements
- [ ] Returns missing fields if validation fails
- [ ] Handles invalid JSON gracefully
- [ ] Handles non-existent templates

### Testing Instructions

**Integration Test:**
```bash
# Get upload URL
UPLOAD_RESPONSE=$(curl -X POST $API_ENDPOINT/seed-data/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test-seed.json", "content_type": "application/json"}')

UPLOAD_URL=$(echo $UPLOAD_RESPONSE | jq -r '.upload_url')
S3_KEY=$(echo $UPLOAD_RESPONSE | jq -r '.s3_key')

# Upload file using presigned URL
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: application/json" \
  -d '{"author": {"name": "Test Author", "biography": "Test bio"}}'

# Validate uploaded data
curl -X POST $API_ENDPOINT/seed-data/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"s3_key\": \"$S3_KEY\", \"template_id\": \"$TEMPLATE_ID\"}"

# Expected: {"valid": true, ...}
```

### Commit Message Template

```
feat(seed-data): add upload and validation endpoints

- Implement POST /seed-data/upload to generate presigned S3 URLs
- Set 15-minute expiration on presigned URLs
- Organize uploaded files by user_id in S3
- Implement POST /seed-data/validate to check data against template schema
- Stream large files to avoid Lambda memory limits
- Return specific missing fields on validation failure

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~16,000

---

## Task 6: Lambda Function - Dashboard API (Real-time Stats)

### Goal

Implement GET /dashboard/{job_id} endpoint that aggregates real-time job progress, cost breakdown, and performance metrics.

### Files to Create

- `backend/lambdas/dashboard/get_stats.py`
- `backend/lambdas/dashboard/requirements.txt`

### Prerequisites

- Tasks 1-3 completed (jobs data available)
- Understanding of cost calculation (ADR-013)
- CostTracking table has data (will be populated by ECS tasks in Phase 4)

### Implementation Steps

1. **Create get_stats handler:**
   - Get job details from Jobs table
   - Query CostTracking table for cost history
   - Calculate current cost breakdown (Bedrock, Fargate, S3)
   - Calculate progress percentage
   - Estimate completion time based on current rate
   - Return dashboard-ready JSON

2. **Dashboard stats implementation:**
   ```python
   from backend.shared.constants import MODEL_PRICING, FARGATE_SPOT_PRICING

   def calculate_cost_breakdown(job_id):
       """Query CostTracking table and sum costs"""
       response = cost_tracking_table.query(
           KeyConditionExpression='job_id = :jid',
           ExpressionAttributeValues={':jid': job_id}
       )

       bedrock_cost = 0.0
       fargate_cost = 0.0
       s3_cost = 0.0

       for item in response['Items']:
           bedrock_cost += item.get('estimated_cost', {}).get('bedrock', 0.0)
           fargate_cost += item.get('estimated_cost', {}).get('fargate', 0.0)
           s3_cost += item.get('estimated_cost', {}).get('s3', 0.0)

       return {
           'bedrock': round(bedrock_cost, 4),
           'fargate': round(fargate_cost, 4),
           's3': round(s3_cost, 4),
           'total': round(bedrock_cost + fargate_cost + s3_cost, 4)
       }

   def estimate_completion(records_generated, target_records, started_at):
       """Estimate completion time based on current rate"""
       if records_generated == 0:
           return None

       elapsed = (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds()
       rate = records_generated / elapsed  # records per second
       remaining = target_records - records_generated

       if rate > 0:
           eta_seconds = remaining / rate
           eta = datetime.utcnow() + timedelta(seconds=eta_seconds)
           return eta.isoformat()
       return None

   def lambda_handler(event, context):
       try:
           user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
           job_id = event['pathParameters']['job_id']

           # Get job
           response = jobs_table.get_item(Key={'job_id': job_id})
           if 'Item' not in response:
               return error_response(404, "Job not found")

           job = response['Item']
           if job['user_id'] != user_id:
               return error_response(403, "Access denied")

           # Calculate stats
           cost_breakdown = calculate_cost_breakdown(job_id)

           target_records = job['config'].get('num_records', 0)
           records_generated = job.get('records_generated', 0)
           progress_pct = (records_generated / target_records * 100) if target_records > 0 else 0

           eta = None
           if job['status'] == 'RUNNING':
               eta = estimate_completion(
                   records_generated,
                   target_records,
                   job.get('started_at', job['created_at'])
               )

           stats = {
               'job_id': job_id,
               'status': job['status'],
               'progress': {
                   'records_generated': records_generated,
                   'target_records': target_records,
                   'percentage': round(progress_pct, 2)
               },
               'cost': cost_breakdown,
               'budget': {
                   'limit': job['budget_limit'],
                   'used': cost_breakdown['total'],
                   'remaining': job['budget_limit'] - cost_breakdown['total'],
                   'percentage_used': round((cost_breakdown['total'] / job['budget_limit'] * 100), 2)
               },
               'timing': {
                   'created_at': job['created_at'],
                   'started_at': job.get('started_at'),
                   'completed_at': job.get('completed_at'),
                   'estimated_completion': eta
               },
               'tokens_used': job.get('tokens_used', 0)
           }

           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps(stats, default=str)
           }

       except Exception as e:
           logger.error(f"Error getting dashboard stats: {str(e)}", exc_info=True)
           return error_response(500, "Internal server error")
   ```

3. **Update API Gateway:**
   - GET /dashboard/{job_id}
   - Attach JWT authorizer

### Verification Checklist

- [ ] Returns complete job stats (progress, cost, timing)
- [ ] Calculates cost breakdown from CostTracking table
- [ ] Computes progress percentage correctly
- [ ] Estimates completion time for running jobs
- [ ] Returns 403 if user doesn't own job
- [ ] Handles jobs with no cost data yet
- [ ] Returns null for ETA if job hasn't started

### Testing Instructions

**Integration Test:**
```bash
# Get dashboard stats for a job
curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/dashboard/$JOB_ID

# Expected output:
# {
#   "job_id": "...",
#   "status": "RUNNING",
#   "progress": {
#     "records_generated": 150,
#     "target_records": 1000,
#     "percentage": 15.0
#   },
#   "cost": {
#     "bedrock": 0.45,
#     "fargate": 0.03,
#     "s3": 0.001,
#     "total": 0.481
#   },
#   "budget": {
#     "limit": 50.0,
#     "used": 0.481,
#     "remaining": 49.519,
#     "percentage_used": 0.96
#   },
#   "timing": {
#     "created_at": "...",
#     "started_at": "...",
#     "estimated_completion": "..."
#   }
# }
```

### Commit Message Template

```
feat(dashboard): add real-time job statistics endpoint

- Implement GET /dashboard/{job_id} for live job stats
- Calculate cost breakdown from CostTracking table
- Compute progress percentage and ETA
- Show budget usage and remaining budget
- Include timing information (created, started, estimated completion)
- Add authorization check for job ownership

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 7: Integration Tests for All APIs

### Goal

Create comprehensive integration test suite covering all API endpoints with various scenarios (success, failure, authorization).

### Files to Create

- `tests/integration/test_jobs_api.py`
- `tests/integration/test_templates_api.py`
- `tests/integration/test_seed_data_api.py`
- `tests/integration/test_dashboard_api.py`
- `tests/integration/conftest.py` - Pytest fixtures

### Prerequisites

- All Phase 3 tasks completed
- pytest and requests libraries installed
- Test Cognito user created

### Implementation Steps

1. **Create conftest.py with shared fixtures:**
   ```python
   import pytest
   import boto3
   import os
   from datetime import datetime

   @pytest.fixture(scope="session")
   def api_endpoint():
       return os.getenv('API_ENDPOINT')

   @pytest.fixture(scope="session")
   def cognito_client():
       return boto3.client('cognito-idp')

   @pytest.fixture(scope="session")
   def auth_token(cognito_client):
       """Get auth token for test user"""
       user_pool_id = os.getenv('USER_POOL_ID')
       client_id = os.getenv('CLIENT_ID')

       # Create test user
       test_email = f"test+{datetime.now().timestamp()}@example.com"
       cognito_client.sign_up(
           ClientId=client_id,
           Username=test_email,
           Password="TestPassword123!",
           UserAttributes=[
               {'Name': 'email', 'Value': test_email}
           ]
       )

       cognito_client.admin_confirm_sign_up(
           UserPoolId=user_pool_id,
           Username=test_email
       )

       response = cognito_client.initiate_auth(
           ClientId=client_id,
           AuthFlow='USER_PASSWORD_AUTH',
           AuthParameters={
               'USERNAME': test_email,
               'PASSWORD': 'TestPassword123!'
           }
       )

       token = response['AuthenticationResult']['IdToken']

       yield token

       # Cleanup
       cognito_client.admin_delete_user(
           UserPoolId=user_pool_id,
           Username=test_email
       )
   ```

2. **Create comprehensive job API tests:**
   - Test create job with valid/invalid config
   - Test list jobs with pagination
   - Test get job by ID
   - Test delete job in various states
   - Test authorization (accessing other user's jobs)

3. **Create template API tests:**
   - Test create template with valid/invalid Jinja2
   - Test list templates (user's + public)
   - Test update template (versioning)
   - Test delete template (prevent if used by jobs)

4. **Create seed data API tests:**
   - Test presigned URL generation
   - Test actual file upload via presigned URL
   - Test validation (valid and invalid data)

5. **Create dashboard API tests:**
   - Test stats endpoint with mock cost data
   - Test progress calculation
   - Test authorization

6. **Add negative test cases:**
   - Missing required fields (400)
   - Invalid JSON syntax (400)
   - Non-existent resources (404)
   - Unauthorized access (403)
   - Server errors (500) - if possible to trigger

### Verification Checklist

- [ ] All API endpoints covered
- [ ] Success and failure scenarios tested
- [ ] Authorization checks validated
- [ ] Pagination tested
- [ ] Edge cases covered (empty lists, missing fields)
- [ ] Tests are idempotent (can run multiple times)
- [ ] Test data cleaned up after execution
- [ ] Tests run in CI/CD pipeline (future)

### Testing Instructions

**Run all integration tests:**
```bash
# Set environment variables
export USER_POOL_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolId')
export CLIENT_ID=$(cat infrastructure/scripts/outputs.json | jq -r '.UserPoolClientId')
export API_ENDPOINT=$(cat infrastructure/scripts/outputs.json | jq -r '.ApiEndpoint')

# Run tests
pytest tests/integration/ -v -s

# Run specific test file
pytest tests/integration/test_jobs_api.py -v

# Run with coverage
pytest tests/integration/ --cov=backend/lambdas --cov-report=html
```

### Commit Message Template

```
test(api): add comprehensive integration tests for all endpoints

- Create pytest fixtures for auth and API endpoint
- Add tests for jobs API (create, list, get, delete)
- Add tests for templates API (CRUD + versioning)
- Add tests for seed data API (upload, validate)
- Add tests for dashboard API (stats, authorization)
- Include negative test cases for error handling
- Implement test data cleanup in fixtures

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Phase 3 Verification

After completing all tasks, verify the entire phase:

### Full Integration Test

1. **End-to-end workflow:**
   ```bash
   # Get auth token
   TOKEN=$(aws cognito-idp initiate-auth ...)

   # Create template
   TEMPLATE_ID=$(curl -X POST $API_ENDPOINT/templates ...)

   # Upload seed data
   UPLOAD_URL=$(curl -X POST $API_ENDPOINT/seed-data/upload ...)
   curl -X PUT "$UPLOAD_URL" --data @seed-data.json

   # Validate seed data
   curl -X POST $API_ENDPOINT/seed-data/validate ...

   # Create job
   JOB_ID=$(curl -X POST $API_ENDPOINT/jobs ...)

   # Get job details
   curl $API_ENDPOINT/jobs/$JOB_ID

   # Get dashboard stats
   curl $API_ENDPOINT/dashboard/$JOB_ID

   # List jobs
   curl $API_ENDPOINT/jobs

   # Cancel job
   curl -X DELETE $API_ENDPOINT/jobs/$JOB_ID
   ```

2. **Run all integration tests:**
   ```bash
   pytest tests/integration/ -v --cov
   ```

### Success Criteria

- [ ] All Lambda functions deployed successfully
- [ ] All API routes functional
- [ ] JWT authorization working on protected endpoints
- [ ] Jobs can be created, listed, retrieved, deleted
- [ ] Templates support full CRUD with versioning
- [ ] Seed data upload via presigned URLs works
- [ ] Seed data validation against template schema works
- [ ] Dashboard returns accurate stats
- [ ] All integration tests pass
- [ ] Cost tracking logic implemented (will be populated in Phase 4)
- [ ] User isolation enforced (users only see their own data)

### Estimated Total Cost (Phase 3 running for 1 hour with 100 API requests)

- Lambda invocations: $0 (free tier)
- API Gateway requests: $0 (free tier)
- DynamoDB reads/writes: $0.01
- S3 presigned URLs: $0
- **Total: ~$0.01/hour**

---

## Known Limitations & Technical Debt

1. **No Batch Operations:** Users must create jobs one at a time (can add batch create later)
2. **Limited Filtering:** List endpoints have basic filtering (can add advanced queries later)
3. **No Template Validation for Models:** Not checking if specified model IDs exist in Bedrock
4. **Large File Uploads:** Presigned URLs timeout at 15 minutes (adequate for most files, but could extend)
5. **No Audit Logging:** Not tracking all API calls (can add AWS CloudTrail integration)
6. **No Rate Limiting per User:** Using API Gateway default throttling (can add per-user quotas)

---

## Next Steps

With the complete backend API layer implemented, you're ready to proceed to **Phase 4: ECS Fargate Generation Workers**.

Phase 4 will add:
- ECS cluster and task definitions
- Fargate Spot capacity provider
- Generation worker container with Bedrock integration
- Checkpoint-based graceful shutdown
- Job queue processing
- Cost tracking updates to DynamoDB

---

**Navigation:**
- [← Back to README](./README.md)
- [← Previous: Phase 2](./Phase-2.md)
- [Next: Phase 4 - ECS Fargate Generation Workers →](./Phase-4.md)
