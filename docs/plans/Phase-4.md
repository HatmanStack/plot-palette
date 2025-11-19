# Phase 4: ECS Fargate Generation Workers

## Phase Goal

Build the core data generation engine using ECS Fargate Spot instances that pull jobs from the DynamoDB queue, generate synthetic data using AWS Bedrock, implement checkpoint-based graceful shutdown for Spot interruptions, and track costs in real-time. By the end of this phase, the system can autonomously process generation jobs end-to-end.

**Success Criteria:**
- ECS cluster configured with Fargate Spot capacity provider
- Docker container image for generation worker built and pushed to ECR
- Worker pulls jobs from DynamoDB queue (QUEUED → RUNNING)
- Worker generates data using Bedrock with template engine integration
- Checkpoint system saves progress to S3 with ETag concurrency control
- SIGTERM handler gracefully shuts down on Spot interruptions
- Cost tracking updates written to DynamoDB CostTracking table
- Budget enforcement stops jobs when limit reached
- Export functionality converts batches to JSONL/Parquet/CSV

**Estimated Tokens:** ~98,000

---

## Prerequisites

- **Phase 1** completed (Infrastructure, S3, DynamoDB, IAM)
- **Phase 2** completed (Authentication)
- **Phase 3** completed (Job API creates jobs in queue)
- Docker installed for building container images
- AWS ECR (Elastic Container Registry) for storing images
- Understanding of ECS Task Definitions and Fargate

---

## Task 1: ECS Cluster and ECR Repository

### Goal

Create ECS cluster, configure Fargate Spot capacity provider, and set up ECR repository for storing worker Docker images.

### Files to Create

- `infrastructure/cloudformation/compute-stack.yaml` - ECS cluster and capacity provider

### Prerequisites

- Phase 1 network stack (VPC, subnets, security groups)
- Phase 1 IAM stack (ECSTaskRole)

### Implementation Steps

1. **Create ECS Cluster:**
   - Cluster name: `plot-palette-cluster-{EnvironmentName}`
   - Enable Container Insights for monitoring
   - Add tags for cost allocation

2. **Create Fargate Capacity Provider:**
   - Name: `FARGATE_SPOT`
   - Strategy: Prioritize Spot capacity
   - Base: 0 (all tasks on Spot)
   - Weight: 1
   - Enable managed termination protection

3. **Create ECR Repository:**
   - Repository name: `plot-palette-worker`
   - Image tag immutability: Enabled (prevent overwriting tags)
   - Image scanning on push: Enabled (security)
   - Lifecycle policy: Keep last 10 images, delete older

4. **Create CloudWatch Log Group:**
   - Log group: `/aws/ecs/plot-palette-worker`
   - Retention: 7 days

5. **CloudFormation template structure:**
   ```yaml
   Resources:
     ECSCluster:
       Type: AWS::ECS::Cluster
       Properties:
         ClusterName: !Sub plot-palette-cluster-${EnvironmentName}
         CapacityProviders:
           - FARGATE_SPOT
         DefaultCapacityProviderStrategy:
           - CapacityProvider: FARGATE_SPOT
             Weight: 1
             Base: 0
         Configuration:
           ExecuteCommandConfiguration:
             Logging: DEFAULT
         ClusterSettings:
           - Name: containerInsights
             Value: enabled

     ECRRepository:
       Type: AWS::ECR::Repository
       Properties:
         RepositoryName: plot-palette-worker
         ImageScanningConfiguration:
           ScanOnPush: true
         ImageTagMutability: MUTABLE
         LifecyclePolicy:
           LifecyclePolicyText: |
             {
               "rules": [{
                 "rulePriority": 1,
                 "description": "Keep last 10 images",
                 "selection": {
                   "tagStatus": "any",
                   "countType": "imageCountMoreThan",
                   "countNumber": 10
                 },
                 "action": {"type": "expire"}
               }]
             }

     WorkerLogGroup:
       Type: AWS::Logs::LogGroup
       Properties:
         LogGroupName: /aws/ecs/plot-palette-worker
         RetentionInDays: 7

   Outputs:
     ClusterName:
       Value: !Ref ECSCluster
       Export:
         Name: !Sub ${AWS::StackName}-ClusterName

     ClusterArn:
       Value: !GetAtt ECSCluster.Arn

     ECRRepositoryUri:
       Value: !GetAtt ECRRepository.RepositoryUri
   ```

6. **Add parameters:**
   - EnvironmentName (from master stack)

### Verification Checklist

- [ ] ECS cluster created
- [ ] Fargate Spot capacity provider configured
- [ ] ECR repository created with lifecycle policy
- [ ] CloudWatch log group created
- [ ] Container Insights enabled
- [ ] Outputs exported for task definition

### Testing Instructions

```bash
# Deploy compute stack
aws cloudformation create-stack \
  --stack-name plot-palette-compute-test \
  --template-body file://infrastructure/cloudformation/compute-stack.yaml \
  --parameters ParameterKey=EnvironmentName,ParameterValue=test

aws cloudformation wait stack-create-complete \
  --stack-name plot-palette-compute-test

# Verify cluster
aws ecs describe-clusters --clusters plot-palette-cluster-test

# Verify ECR repository
aws ecr describe-repositories --repository-names plot-palette-worker

# Verify log group
aws logs describe-log-groups --log-group-name-prefix /aws/ecs/plot-palette-worker
```

### Commit Message Template

```
feat(compute): add ECS cluster with Fargate Spot capacity provider

- Create ECS cluster with Container Insights enabled
- Configure Fargate Spot capacity provider for cost savings
- Create ECR repository for worker Docker images
- Add image scanning and lifecycle policy
- Create CloudWatch log group for worker logs
- Export cluster name and ECR URI for task definitions

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~10,000

---

## Task 2: Worker Docker Container

### Goal

Create Docker container for the generation worker with Python 3.13, dependencies, and application code.

### Files to Create

- `backend/ecs_tasks/worker/Dockerfile` - Container definition
- `backend/ecs_tasks/worker/worker.py` - Main worker script
- `backend/ecs_tasks/worker/requirements.txt` - Python dependencies
- `backend/ecs_tasks/worker/entrypoint.sh` - Container entry point

### Prerequisites

- Docker installed
- ECR repository created (Task 1)
- Understanding of Python async/await for concurrent Bedrock calls

### Implementation Steps

1. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.13-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       curl \
       && rm -rf /var/lib/apt/lists/*

   # Set working directory
   WORKDIR /app

   # Copy requirements and install
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application code
   COPY worker.py .
   COPY entrypoint.sh .
   COPY ../shared /app/shared

   # Make entrypoint executable
   RUN chmod +x entrypoint.sh

   # Set entrypoint
   ENTRYPOINT ["./entrypoint.sh"]
   ```

2. **Create requirements.txt:**
   ```
   boto3>=1.34.0
   requests>=2.31.0
   jinja2>=3.1.2
   pydantic>=2.5.0
   pyarrow>=14.0.0
   pandas>=2.1.0
   ```

3. **Create entrypoint.sh:**
   ```bash
   #!/bin/bash
   set -e

   echo "Starting Plot Palette Worker"
   echo "Region: $AWS_REGION"
   echo "Cluster: $ECS_CLUSTER_NAME"

   # Run worker
   exec python worker.py
   ```

4. **Create worker.py skeleton (detailed implementation in Tasks 3-6):**
   ```python
   import signal
   import sys
   import logging
   import json
   from backend.shared.utils import setup_logger

   logger = setup_logger(__name__)

   class Worker:
       def __init__(self):
           self.shutdown_requested = False
           signal.signal(signal.SIGTERM, self.handle_shutdown)

       def handle_shutdown(self, signum, frame):
           """Handle SIGTERM for Spot interruption"""
           logger.info("Received SIGTERM, initiating graceful shutdown")
           self.shutdown_requested = True

       def run(self):
           """Main worker loop"""
           logger.info("Worker started")
           try:
               while not self.shutdown_requested:
                   self.process_next_job()
           except Exception as e:
               logger.error(f"Worker error: {str(e)}", exc_info=True)
               sys.exit(1)
           finally:
               logger.info("Worker shutdown complete")

       def process_next_job(self):
           """Pull job from queue and process"""
           # Implementation in Task 3
           pass

   if __name__ == "__main__":
       worker = Worker()
       worker.run()
   ```

5. **Build and push Docker image script:**
   Create `infrastructure/scripts/build-and-push-worker.sh`:
   ```bash
   #!/bin/bash
   set -e

   # Get ECR repository URI from CloudFormation
   ECR_URI=$(aws cloudformation describe-stacks \
     --stack-name plot-palette-compute-${ENV:-production} \
     --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
     --output text)

   REGION=$(aws configure get region)

   # Login to ECR
   aws ecr get-login-password --region $REGION | \
     docker login --username AWS --password-stdin $ECR_URI

   # Build image
   cd backend/ecs_tasks/worker
   docker build -t plot-palette-worker:latest .

   # Tag and push
   docker tag plot-palette-worker:latest $ECR_URI:latest
   docker tag plot-palette-worker:latest $ECR_URI:$(git rev-parse --short HEAD)

   docker push $ECR_URI:latest
   docker push $ECR_URI:$(git rev-parse --short HEAD)

   echo "Pushed to $ECR_URI:latest"
   ```

### Verification Checklist

- [ ] Dockerfile builds successfully
- [ ] All dependencies installed
- [ ] Entrypoint script executable
- [ ] Worker.py has proper structure
- [ ] SIGTERM handler registered
- [ ] Image tagged and pushed to ECR
- [ ] Build script works end-to-end

### Testing Instructions

```bash
# Build image locally
cd backend/ecs_tasks/worker
docker build -t plot-palette-worker:test .

# Run container locally (will fail without AWS credentials, but tests build)
docker run plot-palette-worker:test

# Build and push to ECR
chmod +x infrastructure/scripts/build-and-push-worker.sh
./infrastructure/scripts/build-and-push-worker.sh

# Verify image in ECR
aws ecr list-images --repository-name plot-palette-worker
```

### Commit Message Template

```
feat(worker): add Docker container for generation worker

- Create Dockerfile with Python 3.13 base image
- Install dependencies (boto3, jinja2, pandas, pyarrow)
- Add worker.py skeleton with SIGTERM handler
- Create entrypoint script for container initialization
- Add build-and-push script for ECR deployment
- Include shared library in container

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 3: Job Queue Processing

### Goal

Implement queue processing logic to pull jobs from DynamoDB, transition from QUEUED to RUNNING, and update job status.

### Files to Modify

- `backend/ecs_tasks/worker/worker.py` - Add queue processing

### Prerequisites

- Task 2 completed (worker container structure)
- Understanding of DynamoDB conditional writes for queue management

### Implementation Steps

1. **Implement get_next_job method:**
   ```python
   import boto3
   from datetime import datetime

   dynamodb = boto3.resource('dynamodb')
   jobs_table = dynamodb.Table(os.environ['JOBS_TABLE_NAME'])
   queue_table = dynamodb.Table(os.environ['QUEUE_TABLE_NAME'])

   def get_next_job(self):
       """Pull next job from QUEUED status"""
       try:
           # Query for QUEUED jobs (oldest first)
           response = queue_table.query(
               KeyConditionExpression='#status = :queued',
               ExpressionAttributeNames={'#status': 'status'},
               ExpressionAttributeValues={':queued': 'QUEUED'},
               Limit=1,
               ScanIndexForward=True  # Oldest first (FIFO)
           )

           if not response['Items']:
               logger.info("No jobs in queue, sleeping...")
               time.sleep(30)
               return None

           job_item = response['Items'][0]
           job_id = job_item['job_id']

           # Get full job details
           job_response = jobs_table.get_item(Key={'job_id': job_id})
           if 'Item' not in job_response:
               logger.error(f"Job {job_id} in queue but not in Jobs table")
               # Remove from queue
               queue_table.delete_item(
                   Key={
                       'status': 'QUEUED',
                       'job_id#timestamp': job_item['job_id#timestamp']
                   }
               )
               return None

           job = job_response['Item']

           # Atomically move from QUEUED to RUNNING
           try:
               # Update queue table
               queue_table.delete_item(
                   Key={
                       'status': 'QUEUED',
                       'job_id#timestamp': job_item['job_id#timestamp']
                   },
                   ConditionExpression='attribute_exists(#status)',
                   ExpressionAttributeNames={'#status': 'status'}
               )

               # Add to RUNNING queue
               queue_table.put_item(Item={
                   'status': 'RUNNING',
                   'job_id#timestamp': job_item['job_id#timestamp'],
                   'job_id': job_id,
                   'task_arn': os.environ.get('ECS_TASK_ARN', 'local'),
                   'started_at': datetime.utcnow().isoformat()
               })

               # Update job status
               jobs_table.update_item(
                   Key={'job_id': job_id},
                   UpdateExpression='SET #status = :running, started_at = :now, task_arn = :task',
                   ExpressionAttributeNames={'#status': 'status'},
                   ExpressionAttributeValues={
                       ':running': 'RUNNING',
                       ':now': datetime.utcnow().isoformat(),
                       ':task': os.environ.get('ECS_TASK_ARN', 'local')
                   }
               )

               logger.info(f"Claimed job {job_id} and moved to RUNNING")
               return job

           except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
               logger.warning(f"Job {job_id} already claimed by another worker")
               return None

       except Exception as e:
           logger.error(f"Error getting next job: {str(e)}", exc_info=True)
           return None
   ```

2. **Implement process_next_job method:**
   ```python
   def process_next_job(self):
       """Main job processing loop"""
       job = self.get_next_job()

       if job is None:
           return

       try:
           self.generate_data(job)
           self.mark_job_complete(job['job_id'])
       except BudgetExceededError:
           self.mark_job_budget_exceeded(job['job_id'])
       except Exception as e:
           logger.error(f"Error processing job {job['job_id']}: {str(e)}", exc_info=True)
           self.mark_job_failed(job['job_id'], str(e))
   ```

3. **Implement job completion methods:**
   ```python
   def mark_job_complete(self, job_id):
       """Mark job as completed"""
       now = datetime.utcnow().isoformat()

       jobs_table.update_item(
           Key={'job_id': job_id},
           UpdateExpression='SET #status = :status, completed_at = :now, updated_at = :now',
           ExpressionAttributeNames={'#status': 'status'},
           ExpressionAttributeValues={
               ':status': 'COMPLETED',
               ':now': now
           }
       )

       # Move queue item to COMPLETED
       queue_table.query(...)  # Get timestamp
       queue_table.delete_item(...)  # Remove from RUNNING
       queue_table.put_item(...)  # Add to COMPLETED

       logger.info(f"Job {job_id} completed")

   def mark_job_failed(self, job_id, error_message):
       """Mark job as failed"""
       jobs_table.update_item(
           Key={'job_id': job_id},
           UpdateExpression='SET #status = :status, error_message = :error, updated_at = :now',
           ExpressionAttributeNames={'#status': 'status'},
           ExpressionAttributeValues={
               ':status': 'FAILED',
               ':error': error_message,
               ':now': datetime.utcnow().isoformat()
           }
       )
       logger.error(f"Job {job_id} failed: {error_message}")

   def mark_job_budget_exceeded(self, job_id):
       """Mark job as budget exceeded"""
       jobs_table.update_item(
           Key={'job_id': job_id},
           UpdateExpression='SET #status = :status, updated_at = :now',
           ExpressionAttributeNames={'#status': 'status'},
           ExpressionAttributeValues={
               ':status': 'BUDGET_EXCEEDED',
               ':now': datetime.utcnow().isoformat()
           }
       )
       logger.warning(f"Job {job_id} exceeded budget")
   ```

4. **Add environment variables to ECS Task Definition (Task 5):**
   - JOBS_TABLE_NAME
   - QUEUE_TABLE_NAME
   - ECS_TASK_ARN (injected by ECS)

### Verification Checklist

- [ ] Worker pulls oldest job from QUEUED status
- [ ] Queue transition is atomic (no race conditions)
- [ ] Job status updates to RUNNING
- [ ] Worker sleeps when queue is empty
- [ ] Multiple workers don't claim same job
- [ ] Job completion updates all tables correctly
- [ ] Failed jobs marked appropriately
- [ ] Budget exceeded status recorded

### Testing Instructions

**Unit Test:**
```python
import pytest
from unittest.mock import Mock, patch
from backend.ecs_tasks.worker.worker import Worker

@patch('backend.ecs_tasks.worker.worker.queue_table')
@patch('backend.ecs_tasks.worker.worker.jobs_table')
def test_get_next_job(mock_jobs, mock_queue):
    mock_queue.query.return_value = {
        'Items': [{
            'status': 'QUEUED',
            'job_id': 'job-123',
            'job_id#timestamp': 'job-123#2025-11-19T10:00:00Z'
        }]
    }
    mock_jobs.get_item.return_value = {
        'Item': {
            'job_id': 'job-123',
            'config': {},
            'budget_limit': 100
        }
    }

    worker = Worker()
    job = worker.get_next_job()

    assert job is not None
    assert job['job_id'] == 'job-123'
    mock_queue.delete_item.assert_called_once()
    mock_jobs.update_item.assert_called_once()
```

### Commit Message Template

```
feat(worker): implement job queue processing and status management

- Add get_next_job to pull from DynamoDB queue
- Implement atomic QUEUED → RUNNING transition
- Prevent race conditions with conditional writes
- Add job completion/failure status updates
- Handle budget exceeded state
- Sleep when queue is empty
- Support concurrent workers without conflicts

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~16,000

---

## Task 4: Data Generation with Bedrock Integration

### Goal

Implement the core data generation logic using AWS Bedrock, template engine integration, and seed data loading.

### Files to Modify

- `backend/ecs_tasks/worker/worker.py` - Add generate_data method
- `backend/ecs_tasks/worker/template_engine.py` - Template rendering logic

### Prerequisites

- Task 3 completed (job processing)
- Understanding of template structure from Phase 3
- AWS Bedrock API knowledge

### Implementation Steps

1. **Create template_engine.py:**
   ```python
   import jinja2
   import json
   from typing import Dict, Any

   class TemplateEngine:
       def __init__(self):
           self.env = jinja2.Environment(
               autoescape=False,
               trim_blocks=True,
               lstrip_blocks=True
           )

       def render_step(self, step_def: Dict, context: Dict[str, Any]) -> str:
           """Render a single template step"""
           template = self.env.from_string(step_def['prompt'])
           return template.render(**context)

       def execute_template(self, template_def: Dict, seed_data: Dict, bedrock_client) -> Dict:
           """Execute multi-step template with Bedrock calls"""
           context = seed_data.copy()
           results = {}

           for step in template_def.get('steps', []):
               step_id = step['id']
               model_id = step['model']

               # Render prompt with current context
               prompt = self.render_step(step, context)

               # Call Bedrock
               response = self.call_bedrock(bedrock_client, model_id, prompt)

               # Store step result
               results[step_id] = {
                   'prompt': prompt,
                   'output': response,
                   'model': model_id
               }

               # Add to context for next steps
               context[f'steps.{step_id}.output'] = response

           return results

       def call_bedrock(self, client, model_id: str, prompt: str) -> str:
           """Call AWS Bedrock API"""
           # Model-specific request formatting
           if 'claude' in model_id:
               request_body = {
                   "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                   "max_tokens_to_sample": 2000,
                   "temperature": 0.7
               }
           elif 'llama' in model_id:
               request_body = {
                   "prompt": prompt,
                   "max_gen_len": 2000,
                   "temperature": 0.7
               }
           else:
               request_body = {"prompt": prompt}

           response = client.invoke_model(
               modelId=model_id,
               body=json.dumps(request_body)
           )

           response_body = json.loads(response['body'].read())

           # Extract text based on model
           if 'claude' in model_id:
               return response_body['completion']
           elif 'llama' in model_id:
               return response_body['generation']
           else:
               return response_body.get('text', '')
   ```

2. **Implement generate_data method in worker.py:**
   ```python
   import boto3
   import random
   from template_engine import TemplateEngine

   bedrock_client = boto3.client('bedrock-runtime')
   s3_client = boto3.client('s3')
   template_engine = TemplateEngine()

   def generate_data(self, job):
       """Main data generation loop"""
       job_id = job['job_id']
       config = job['config']

       # Load template
       template = self.load_template(config['template_id'])

       # Load seed data
       seed_data_list = self.load_seed_data(config['seed_data_path'])

       # Load or create checkpoint
       checkpoint = self.load_checkpoint(job_id)
       start_index = checkpoint.get('records_generated', 0)

       target_records = config['num_records']
       budget_limit = job['budget_limit']

       logger.info(f"Generating {target_records} records for job {job_id}, starting at {start_index}")

       batch_records = []
       batch_number = checkpoint.get('current_batch', 1)

       for i in range(start_index, target_records):
           if self.shutdown_requested:
               logger.info("Shutdown requested, checkpointing and exiting")
               self.save_checkpoint(job_id, checkpoint)
               break

           # Check budget before each generation
           current_cost = self.calculate_current_cost(job_id)
           if current_cost >= budget_limit:
               logger.warning(f"Budget limit reached: ${current_cost:.2f} >= ${budget_limit:.2f}")
               raise BudgetExceededError(f"Exceeded budget limit of ${budget_limit}")

           # Select random seed data
           seed_data = random.choice(seed_data_list)

           # Generate record using template
           try:
               result = template_engine.execute_template(
                   template['template_definition'],
                   seed_data,
                   bedrock_client
               )

               record = {
                   'id': f"{job_id}-{i}",
                   'job_id': job_id,
                   'timestamp': datetime.utcnow().isoformat(),
                   'seed_data_keys': seed_data.get('_id'),  # Track which seed data used
                   'generation_result': result
               }

               batch_records.append(record)

               # Update counters
               checkpoint['records_generated'] = i + 1
               checkpoint['tokens_used'] = checkpoint.get('tokens_used', 0) + self.estimate_tokens(result)

               # Checkpoint every N records
               if (i + 1) % self.CHECKPOINT_INTERVAL == 0:
                   self.save_batch(job_id, batch_number, batch_records)
                   self.save_checkpoint(job_id, checkpoint)
                   self.update_cost_tracking(job_id, checkpoint)
                   self.update_job_progress(job_id, checkpoint)

                   batch_records = []
                   batch_number += 1

           except Exception as e:
               logger.error(f"Error generating record {i}: {str(e)}")
               # Continue with next record (don't fail entire job)
               continue

       # Save final batch
       if batch_records:
           self.save_batch(job_id, batch_number, batch_records)

       # Final checkpoint
       checkpoint['completed'] = True
       self.save_checkpoint(job_id, checkpoint)

       # Export data
       self.export_data(job_id, config)

       logger.info(f"Job {job_id} completed: {checkpoint['records_generated']} records generated")
   ```

3. **Implement helper methods:**
   ```python
   def load_template(self, template_id):
       """Load template from DynamoDB"""
       response = templates_table.get_item(
           Key={'template_id': template_id, 'version': 1}
       )
       return response['Item']

   def load_seed_data(self, s3_path):
       """Load seed data from S3"""
       bucket = os.environ['BUCKET_NAME']
       # s3_path format: "seed-data/user-123/data.json"

       response = s3_client.get_object(Bucket=bucket, Key=s3_path)
       data = json.loads(response['Body'].read())

       # Support both single dict and list of dicts
       if isinstance(data, list):
           return data
       else:
           return [data]

   def estimate_tokens(self, result):
       """Estimate tokens used in generation (rough approximation)"""
       text = json.dumps(result)
       return len(text) // 4  # Rough estimate: 1 token ~= 4 characters

   class BudgetExceededError(Exception):
       pass
   ```

### Verification Checklist

- [ ] Template loaded from DynamoDB correctly
- [ ] Seed data loaded from S3
- [ ] Multi-step templates execute in order
- [ ] Bedrock API calls formatted correctly for each model
- [ ] Random seed data selection works
- [ ] Budget check runs before each generation
- [ ] Tokens estimated and tracked
- [ ] Errors in single records don't fail entire job
- [ ] Generation respects shutdown signal

### Testing Instructions

**Unit Test:**
```python
def test_template_engine():
    engine = TemplateEngine()

    template_def = {
        'steps': [{
            'id': 'question',
            'model': 'claude-sonnet',
            'prompt': 'Generate a question about {{ topic }}'
        }]
    }

    seed_data = {'topic': 'Python'}

    # Mock Bedrock client
    mock_bedrock = Mock()
    mock_bedrock.invoke_model.return_value = {
        'body': Mock(read=lambda: json.dumps({'completion': 'What is Python?'}).encode())
    }

    result = engine.execute_template(template_def, seed_data, mock_bedrock)

    assert 'question' in result
    assert result['question']['output'] == 'What is Python?'
```

### Commit Message Template

```
feat(worker): implement data generation with Bedrock integration

- Create TemplateEngine class for multi-step template execution
- Implement Bedrock API calls with model-specific formatting
- Add generate_data method with budget checking
- Load templates from DynamoDB and seed data from S3
- Implement token estimation and tracking
- Support random seed data selection
- Handle per-record errors gracefully
- Respect shutdown signal during generation

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~18,000

---

## Task 5: Checkpoint System with S3 ETags

### Goal

Implement robust checkpoint system using S3 with ETag-based concurrency control for graceful shutdown and job resumption.

### Files to Modify

- `backend/ecs_tasks/worker/worker.py` - Add checkpoint methods

### Prerequisites

- Task 4 completed (data generation)
- Understanding of S3 ETags and conditional writes

### Implementation Steps

1. **Implement load_checkpoint:**
   ```python
   def load_checkpoint(self, job_id):
       """Load checkpoint from S3, return empty dict if not exists"""
       bucket = os.environ['BUCKET_NAME']
       key = f"jobs/{job_id}/checkpoint.json"

       try:
           response = s3_client.get_object(Bucket=bucket, Key=key)
           etag = response['ETag'].strip('"')  # Remove quotes
           checkpoint_data = json.loads(response['Body'].read())
           checkpoint_data['_etag'] = etag  # Store for conditional writes

           logger.info(f"Loaded checkpoint for job {job_id}: {checkpoint_data['records_generated']} records")
           return checkpoint_data

       except s3_client.exceptions.NoSuchKey:
           logger.info(f"No checkpoint found for job {job_id}, starting fresh")
           return {
               'job_id': job_id,
               'records_generated': 0,
               'current_batch': 1,
               'tokens_used': 0,
               'cost_accumulated': 0.0,
               'last_updated': datetime.utcnow().isoformat()
           }
       except Exception as e:
           logger.error(f"Error loading checkpoint: {str(e)}")
           # Return empty checkpoint on error
           return {'job_id': job_id, 'records_generated': 0}
   ```

2. **Implement save_checkpoint with ETag:**
   ```python
   def save_checkpoint(self, job_id, checkpoint_data):
       """Save checkpoint to S3 with ETag-based concurrency control"""
       bucket = os.environ['BUCKET_NAME']
       key = f"jobs/{job_id}/checkpoint.json"

       checkpoint_data['last_updated'] = datetime.utcnow().isoformat()

       # Extract ETag if exists
       etag = checkpoint_data.pop('_etag', None)

       checkpoint_json = json.dumps(checkpoint_data, indent=2)

       try:
           if etag:
               # Conditional write - only if ETag matches
               s3_client.put_object(
                   Bucket=bucket,
                   Key=key,
                   Body=checkpoint_json,
                   ContentType='application/json',
                   IfMatch=etag  # Fail if ETag changed
               )
           else:
               # First write - use If-None-Match to prevent overwrite
               s3_client.put_object(
                   Bucket=bucket,
                   Key=key,
                   Body=checkpoint_json,
                   ContentType='application/json',
                   IfNoneMatch='*'  # Fail if file already exists
               )

           logger.info(f"Saved checkpoint for job {job_id}: {checkpoint_data['records_generated']} records")

       except s3_client.exceptions.PreconditionFailed:
           logger.warning(f"Checkpoint ETag mismatch for job {job_id}, reloading and merging")
           # Another task updated checkpoint - reload and merge
           current_checkpoint = self.load_checkpoint(job_id)

           # Merge strategy: take maximum records_generated
           if checkpoint_data['records_generated'] > current_checkpoint['records_generated']:
               # Retry save with new ETag
               checkpoint_data['_etag'] = current_checkpoint['_etag']
               self.save_checkpoint(job_id, checkpoint_data)
           else:
               logger.info("Current checkpoint is already ahead, skipping save")

       except Exception as e:
           logger.error(f"Error saving checkpoint: {str(e)}", exc_info=True)
           raise
   ```

3. **Implement save_batch:**
   ```python
   def save_batch(self, job_id, batch_number, records):
       """Save batch of generated records to S3"""
       if not records:
           return

       bucket = os.environ['BUCKET_NAME']
       key = f"jobs/{job_id}/outputs/batch-{batch_number:04d}.jsonl"

       # Write as JSONL (one JSON object per line)
       jsonl_content = '\n'.join([json.dumps(record) for record in records])

       s3_client.put_object(
           Bucket=bucket,
           Key=key,
           Body=jsonl_content.encode('utf-8'),
           ContentType='application/x-ndjson'
       )

       logger.info(f"Saved batch {batch_number} for job {job_id}: {len(records)} records")
   ```

4. **Implement graceful shutdown:**
   ```python
   def handle_shutdown(self, signum, frame):
       """Handle SIGTERM for Spot interruption (120 seconds to shutdown)"""
       logger.info("Received SIGTERM (Spot interruption), initiating graceful shutdown")
       self.shutdown_requested = True

       # Set alarm to force exit after 100 seconds (leave 20s buffer)
       signal.alarm(100)

   def run(self):
       """Main worker loop with shutdown handling"""
       logger.info("Worker started")

       try:
           while not self.shutdown_requested:
               self.process_next_job()

       except Exception as e:
           logger.error(f"Worker error: {str(e)}", exc_info=True)
           sys.exit(1)

       finally:
           logger.info("Worker shutdown complete")
           sys.exit(0)
   ```

### Verification Checklist

- [ ] Checkpoint loads from S3 with ETag
- [ ] Checkpoint saves with conditional writes
- [ ] ETag mismatch handled gracefully (reload and merge)
- [ ] Batches saved as JSONL files
- [ ] SIGTERM handler triggers shutdown
- [ ] Worker has 120 seconds to shutdown cleanly
- [ ] Resume from checkpoint works correctly
- [ ] Concurrent workers don't corrupt checkpoints

### Testing Instructions

**Integration Test:**
```python
def test_checkpoint_concurrency():
    """Test that concurrent workers don't corrupt checkpoints"""
    job_id = "test-job-123"

    # Simulate two workers
    worker1 = Worker()
    worker2 = Worker()

    checkpoint1 = worker1.load_checkpoint(job_id)
    checkpoint2 = worker2.load_checkpoint(job_id)

    # Both update
    checkpoint1['records_generated'] = 50
    checkpoint2['records_generated'] = 45

    # Save both
    worker1.save_checkpoint(job_id, checkpoint1)
    worker2.save_checkpoint(job_id, checkpoint2)

    # Load final - should be 50 (maximum)
    final = worker1.load_checkpoint(job_id)
    assert final['records_generated'] == 50
```

### Commit Message Template

```
feat(worker): implement checkpoint system with S3 ETag concurrency control

- Add load_checkpoint to resume from S3
- Implement save_checkpoint with ETag-based conditional writes
- Handle ETag mismatches with reload and merge strategy
- Add save_batch for incremental output storage
- Implement graceful shutdown for Spot interruptions (120s window)
- Prevent checkpoint corruption from concurrent workers
- Support job resumption after interruption

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~16,000

---

## Task 6: Cost Tracking and Budget Enforcement

### Goal

Implement real-time cost tracking to DynamoDB CostTracking table and budget enforcement to stop jobs before exceeding limits.

### Files to Modify

- `backend/ecs_tasks/worker/worker.py` - Add cost tracking methods

### Prerequisites

- Task 4 completed (generation with token counting)
- Understanding of pricing constants from Phase 1 shared library

### Implementation Steps

1. **Implement update_cost_tracking:**
   ```python
   from backend.shared.constants import MODEL_PRICING, FARGATE_SPOT_PRICING, S3_PRICING

   def update_cost_tracking(self, job_id, checkpoint):
       """Write cost tracking record to DynamoDB"""
       tokens_used = checkpoint.get('tokens_used', 0)
       records_generated = checkpoint.get('records_generated', 0)

       # Calculate Bedrock cost (simplified - assumes single model)
       # In reality, track per-model usage
       bedrock_cost = (tokens_used / 1_000_000) * MODEL_PRICING['claude-sonnet']['input']

       # Calculate Fargate cost
       elapsed_seconds = (
           datetime.utcnow() - datetime.fromisoformat(checkpoint.get('started_at', datetime.utcnow().isoformat()))
       ).total_seconds()
       fargate_hours = elapsed_seconds / 3600
       fargate_cost = fargate_hours * FARGATE_SPOT_PRICING['vcpu'] * 0.5  # Assuming 0.5 vCPU

       # Calculate S3 cost
       s3_puts = checkpoint.get('current_batch', 1) + 1  # Batches + checkpoint
       s3_cost = (s3_puts / 1000) * S3_PRICING['put']

       total_cost = bedrock_cost + fargate_cost + s3_cost

       # Write to DynamoDB
       cost_tracking_table.put_item(Item={
           'job_id': job_id,
           'timestamp': datetime.utcnow().isoformat(),
           'bedrock_tokens': tokens_used,
           'fargate_hours': fargate_hours,
           's3_operations': s3_puts,
           'estimated_cost': {
               'bedrock': round(bedrock_cost, 4),
               'fargate': round(fargate_cost, 4),
               's3': round(s3_cost, 4),
               'total': round(total_cost, 4)
           },
           'records_generated': records_generated,
           'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())  # 90-day retention
       })

       logger.info(f"Updated cost tracking for job {job_id}: ${total_cost:.4f}")

       return total_cost
   ```

2. **Implement calculate_current_cost:**
   ```python
   def calculate_current_cost(self, job_id):
       """Query cost tracking table and sum total cost"""
       try:
           response = cost_tracking_table.query(
               KeyConditionExpression='job_id = :jid',
               ExpressionAttributeValues={':jid': job_id},
               ScanIndexForward=False,  # Descending order
               Limit=1  # Just get latest entry
           )

           if response['Items']:
               return response['Items'][0]['estimated_cost']['total']
           else:
               return 0.0

       except Exception as e:
           logger.error(f"Error calculating cost: {str(e)}")
           return 0.0  # Fail open to avoid blocking generation
   ```

3. **Implement update_job_progress:**
   ```python
   def update_job_progress(self, job_id, checkpoint):
       """Update job record with current progress"""
       jobs_table.update_item(
           Key={'job_id': job_id},
           UpdateExpression='''
               SET records_generated = :records,
                   tokens_used = :tokens,
                   cost_estimate = :cost,
                   updated_at = :now
           ''',
           ExpressionAttributeValues={
               ':records': checkpoint['records_generated'],
               ':tokens': checkpoint.get('tokens_used', 0),
               ':cost': checkpoint.get('cost_accumulated', 0.0),
               ':now': datetime.utcnow().isoformat()
           }
       )
   ```

4. **Integrate cost tracking into worker's generation loop:**

In `generate_data` method (from Task 4), add cost tracking after each batch and checkpoint:

```python
# In the generation loop, after generating each batch:
for batch in self.generate_batches(seed_data, template, model):
    # Generate data
    generated_records = self.call_bedrock(batch)

    # Save batch to S3
    self.save_batch(job_id, batch_num, generated_records)

    # Update checkpoint
    checkpoint['records_generated'] += len(generated_records)
    checkpoint['tokens_used'] += generated_records['total_tokens']
    checkpoint['current_batch'] = batch_num

    # **Write cost tracking record**
    total_cost = self.update_cost_tracking(job_id, checkpoint)

    # **Check budget before continuing**
    if total_cost >= budget_limit:
        logger.warning(f"Budget limit reached: ${total_cost:.2f} >= ${budget_limit:.2f}")
        self.update_job_status(job_id, 'BUDGET_EXCEEDED')
        raise BudgetExceededError(f"Exceeded budget limit of ${budget_limit}")

    # Update job progress in Jobs table
    self.update_job_progress(job_id, checkpoint)

    # Save checkpoint
    if batch_num % CHECKPOINT_INTERVAL == 0:
        self.save_checkpoint(job_id, checkpoint)

    batch_num += 1
```

**Key Integration Points:**
- Cost tracking is written **after each batch** (not just at checkpoints)
- Budget is checked **before continuing to next batch**
- Job status updated to `BUDGET_EXCEEDED` if limit hit
- Cost records written with 90-day TTL for cleanup

5. **Add constants to shared library (if not already there):**
   ```python
   # backend/shared/constants.py
   MODEL_PRICING = {
       'claude-sonnet': {'input': 3.00, 'output': 15.00},  # per 1M tokens
       'llama-3.1-70b': {'input': 0.99, 'output': 0.99},
       'llama-3.1-8b': {'input': 0.30, 'output': 0.60},
       'mistral-7b': {'input': 0.15, 'output': 0.20}
   }

   FARGATE_SPOT_PRICING = {
       'vcpu': 0.01246,  # per vCPU-hour
       'memory': 0.00127  # per GB-hour
   }

   S3_PRICING = {
       'put': 0.005,  # per 1000 PUT requests
       'get': 0.0004   # per 1000 GET requests
   }
   ```

### Verification Checklist

- [ ] Cost tracking records written to DynamoDB
- [ ] TTL set for 90-day retention
- [ ] Bedrock, Fargate, and S3 costs calculated correctly
- [ ] Budget check runs before each generation
- [ ] Job stops when budget exceeded
- [ ] Job progress updated periodically
- [ ] Cost calculation handles missing data gracefully
- [ ] Pricing constants accurate and up-to-date

### Testing Instructions

**Unit Test:**
```python
def test_cost_calculation():
    worker = Worker()

    checkpoint = {
        'tokens_used': 1_000_000,  # 1M tokens
        'current_batch': 20,
        'started_at': (datetime.utcnow() - timedelta(hours=1)).isoformat()
    }

    cost = worker.update_cost_tracking('test-job', checkpoint)

    # Approximate costs:
    # Bedrock: 1M tokens * $3/M = $3.00
    # Fargate: 1 hour * 0.5 vCPU * $0.01246 = $0.00623
    # S3: 21 PUTs * $0.005/1000 = $0.000105
    # Total: ~$3.006

    assert cost > 3.0 and cost < 3.01
```

### Commit Message Template

```
feat(worker): implement real-time cost tracking and budget enforcement

- Add update_cost_tracking to write to DynamoDB CostTracking table
- Calculate Bedrock, Fargate, and S3 costs separately
- Implement calculate_current_cost to query latest cost
- Add budget check before each generation
- Stop job and raise BudgetExceededError when limit reached
- Update job progress periodically
- Set 90-day TTL on cost tracking records

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Task 7: Data Export (JSONL, Parquet, CSV)

### Goal

Implement export functionality to convert batch files into final dataset formats (JSONL, Parquet, CSV) when job completes.

### Files to Modify

- `backend/ecs_tasks/worker/worker.py` - Add export_data method

### Prerequisites

- Task 4 completed (batch files saved)
- pandas and pyarrow installed

### Implementation Steps

1. **Implement export_data:**
   ```python
   import pandas as pd
   import pyarrow as pa
   import pyarrow.parquet as pq

   def export_data(self, job_id, config):
       """Export batch files to final formats"""
       logger.info(f"Exporting data for job {job_id}")

       output_format = config.get('output_format', 'JSONL')
       partition_strategy = config.get('partition_strategy', 'none')

       # Load all batch files
       records = self.load_all_batches(job_id)

       if not records:
           logger.warning(f"No records to export for job {job_id}")
           return

       bucket = os.environ['BUCKET_NAME']

       # Export based on format
       if output_format == 'JSONL' or 'JSONL' in output_format:
           self.export_jsonl(job_id, records, partition_strategy, bucket)

       if output_format == 'PARQUET' or 'PARQUET' in output_format:
           self.export_parquet(job_id, records, partition_strategy, bucket)

       if output_format == 'CSV' or 'CSV' in output_format:
           self.export_csv(job_id, records, partition_strategy, bucket)

       logger.info(f"Export complete for job {job_id}")
   ```

2. **Implement load_all_batches:**
   ```python
   def load_all_batches(self, job_id):
       """Load all batch files from S3"""
       bucket = os.environ['BUCKET_NAME']
       prefix = f"jobs/{job_id}/outputs/"

       records = []

       paginator = s3_client.get_paginator('list_objects_v2')
       for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
           if 'Contents' not in page:
               continue

           for obj in page['Contents']:
               key = obj['Key']
               if not key.endswith('.jsonl'):
                   continue

               # Download batch file
               response = s3_client.get_object(Bucket=bucket, Key=key)
               content = response['Body'].read().decode('utf-8')

               # Parse JSONL
               for line in content.strip().split('\n'):
                   if line:
                       records.append(json.loads(line))

       logger.info(f"Loaded {len(records)} records from batches")
       return records
   ```

3. **Implement export_jsonl:**
   ```python
   def export_jsonl(self, job_id, records, partition_strategy, bucket):
       """Export as JSONL format"""
       if partition_strategy == 'none':
           # Single file
           key = f"jobs/{job_id}/exports/dataset.jsonl"
           jsonl_content = '\n'.join([json.dumps(record) for record in records])
           s3_client.put_object(
               Bucket=bucket,
               Key=key,
               Body=jsonl_content.encode('utf-8'),
               ContentType='application/x-ndjson'
           )
           logger.info(f"Exported JSONL: {key}")

       elif partition_strategy == 'timestamp':
           # Partition by date
           partitions = {}
           for record in records:
               timestamp = record['timestamp'][:10]  # YYYY-MM-DD
               if timestamp not in partitions:
                   partitions[timestamp] = []
               partitions[timestamp].append(record)

           for date, date_records in partitions.items():
               key = f"jobs/{job_id}/exports/partitioned/date={date}/records.jsonl"
               jsonl_content = '\n'.join([json.dumps(r) for r in date_records])
               s3_client.put_object(Bucket=bucket, Key=key, Body=jsonl_content.encode('utf-8'))

           logger.info(f"Exported {len(partitions)} date partitions")
   ```

4. **Implement export_parquet:**
   ```python
   def export_parquet(self, job_id, records, partition_strategy, bucket):
       """Export as Parquet format"""
       # Flatten nested JSON for Parquet
       flattened_records = []
       for record in records:
           flat = {
               'id': record['id'],
               'job_id': record['job_id'],
               'timestamp': record['timestamp'],
               'generation_result': json.dumps(record['generation_result'])  # Serialize nested JSON
           }
           flattened_records.append(flat)

       # Convert to pandas DataFrame
       df = pd.DataFrame(flattened_records)

       # Convert to PyArrow Table
       table = pa.Table.from_pandas(df)

       # Write Parquet
       if partition_strategy == 'none':
           key = f"jobs/{job_id}/exports/dataset.parquet"

           # Write to buffer
           import io
           buffer = io.BytesIO()
           pq.write_table(table, buffer)

           # Upload to S3
           buffer.seek(0)
           s3_client.put_object(
               Bucket=bucket,
               Key=key,
               Body=buffer.read(),
               ContentType='application/octet-stream'
           )

           logger.info(f"Exported Parquet: {key}")

       # (Partition strategy implementation similar to JSONL)
   ```

5. **Implement export_csv:**
   ```python
   def export_csv(self, job_id, records, partition_strategy, bucket):
       """Export as CSV format"""
       # Flatten records
       flattened_records = []
       for record in records:
           flat = {
               'id': record['id'],
               'job_id': record['job_id'],
               'timestamp': record['timestamp'],
               'generation_result': json.dumps(record['generation_result'])
           }
           flattened_records.append(flat)

       df = pd.DataFrame(flattened_records)

       # Convert to CSV
       csv_content = df.to_csv(index=False)

       key = f"jobs/{job_id}/exports/dataset.csv"
       s3_client.put_object(
           Bucket=bucket,
           Key=key,
           Body=csv_content.encode('utf-8'),
           ContentType='text/csv'
       )

       logger.info(f"Exported CSV: {key}")
   ```

### Verification Checklist

- [ ] Loads all batch files from S3
- [ ] Exports to JSONL format
- [ ] Exports to Parquet format with flattened schema
- [ ] Exports to CSV format
- [ ] Supports single file and partitioned exports
- [ ] Handles large datasets without memory issues
- [ ] Exported files accessible via S3

### Testing Instructions

**Integration Test:**
```bash
# After job completes, check exports
aws s3 ls s3://$BUCKET_NAME/jobs/$JOB_ID/exports/

# Download and verify JSONL
aws s3 cp s3://$BUCKET_NAME/jobs/$JOB_ID/exports/dataset.jsonl .
head dataset.jsonl

# Download and verify Parquet
aws s3 cp s3://$BUCKET_NAME/jobs/$JOB_ID/exports/dataset.parquet .
python -c "import pandas as pd; df = pd.read_parquet('dataset.parquet'); print(df.head())"

# Download and verify CSV
aws s3 cp s3://$BUCKET_NAME/jobs/$JOB_ID/exports/dataset.csv .
head dataset.csv
```

### Commit Message Template

```
feat(worker): implement multi-format data export (JSONL, Parquet, CSV)

- Add export_data method to convert batch files to final formats
- Implement JSONL export with optional partitioning
- Implement Parquet export with flattened schema
- Implement CSV export with pandas
- Support timestamp-based partitioning
- Handle large datasets with streaming where possible
- Upload exports to S3 for user download

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Task 8: ECS Task Definition and Service

### Goal

Create ECS Task Definition for the worker container and configure ECS Service to run tasks on Fargate Spot.

### Files to Create

- `infrastructure/cloudformation/ecs-task-definition.yaml` - Task definition template

### Prerequisites

- Task 1 completed (ECS cluster, ECR repository)
- Task 2 completed (Docker image built and pushed)
- Phase 1 IAM stack (ECSTaskRole)

### Implementation Steps

1. **Create Task Definition:**
   ```yaml
   Resources:
     WorkerTaskDefinition:
       Type: AWS::ECS::TaskDefinition
       Properties:
         Family: plot-palette-worker
         NetworkMode: awsvpc
         RequiresCompatibilities:
           - FARGATE
         Cpu: 512  # 0.5 vCPU (configurable)
         Memory: 1024  # 1 GB (configurable)
         TaskRoleArn: !Ref ECSTaskRoleArn
         ExecutionRoleArn: !Ref ECSTaskRoleArn  # For pulling image from ECR
         ContainerDefinitions:
           - Name: worker
             Image: !Sub ${ECRRepositoryUri}:latest
             Essential: true
             LogConfiguration:
               LogDriver: awslogs
               Options:
                 awslogs-group: /aws/ecs/plot-palette-worker
                 awslogs-region: !Ref AWS::Region
                 awslogs-stream-prefix: worker
             Environment:
               - Name: AWS_REGION
                 Value: !Ref AWS::Region
               - Name: JOBS_TABLE_NAME
                 Value: !Ref JobsTableName
               - Name: QUEUE_TABLE_NAME
                 Value: !Ref QueueTableName
               - Name: TEMPLATES_TABLE_NAME
                 Value: !Ref TemplatesTableName
               - Name: COST_TRACKING_TABLE_NAME
                 Value: !Ref CostTrackingTableName
               - Name: BUCKET_NAME
                 Value: !Ref BucketName
               - Name: ECS_CLUSTER_NAME
                 Value: !Ref ClusterName
               - Name: CHECKPOINT_INTERVAL
                 Value: "50"
             StopTimeout: 120  # 2 minutes for graceful shutdown

   Parameters:
     ECSTaskRoleArn:
       Type: String
     ECRRepositoryUri:
       Type: String
     JobsTableName:
       Type: String
     QueueTableName:
       Type: String
     TemplatesTableName:
       Type: String
     CostTrackingTableName:
       Type: String
     BucketName:
       Type: String
     ClusterName:
       Type: String

   Outputs:
     TaskDefinitionArn:
       Value: !Ref WorkerTaskDefinition
   ```

2. **Create Lambda function to start ECS tasks (triggered by API):**
   - Phase 3 Lambda functions (create_job) should trigger ECS task
   - Add to Phase 3 create_job Lambda:
   ```python
   import boto3

   ecs_client = boto3.client('ecs')

   def start_worker_task(job_id):
       """Start ECS Fargate task for job processing"""
       response = ecs_client.run_task(
           cluster=os.environ['ECS_CLUSTER_NAME'],
           taskDefinition='plot-palette-worker',
           launchType='FARGATE',
           networkConfiguration={
               'awsvpcConfiguration': {
                   'subnets': os.environ['SUBNET_IDS'].split(','),
                   'securityGroups': [os.environ['SECURITY_GROUP_ID']],
                   'assignPublicIp': 'ENABLED'
               }
           },
           capacityProviderStrategy=[{
               'capacityProvider': 'FARGATE_SPOT',
               'weight': 1,
               'base': 0
           }],
           enableExecuteCommand=True,  # For debugging
           tags=[
               {'key': 'job-id', 'value': job_id},
               {'key': 'application', 'value': 'plot-palette'}
           ]
       )

       task_arn = response['tasks'][0]['taskArn']
       logger.info(f"Started ECS task {task_arn} for job {job_id}")

       return task_arn
   ```

3. **Note on ECS Service vs run_task:**
   - We use `run_task` (not ECS Service) because each job is independent
   - Service would maintain desired count, but we want tasks to complete and exit
   - Task starts when job created, processes queue, exits when queue empty or after processing its job

4. **Modify worker to process single job then exit:**
   ```python
   def run(self):
       """Process one job then exit (not infinite loop)"""
       logger.info("Worker started")

       try:
           job = self.get_next_job()

           if job:
               self.generate_data(job)
               self.mark_job_complete(job['job_id'])
           else:
               logger.info("No jobs in queue")

       except Exception as e:
           logger.error(f"Worker error: {str(e)}", exc_info=True)
           sys.exit(1)

       finally:
           logger.info("Worker shutdown")
           sys.exit(0)
   ```

### Verification Checklist

- [ ] Task definition created with correct CPU/memory
- [ ] Environment variables passed to container
- [ ] Task role attached with correct permissions
- [ ] CloudWatch logs configured
- [ ] Stop timeout set to 120 seconds
- [ ] Task can be started via run_task API
- [ ] Task runs on Fargate Spot
- [ ] Task exits after processing job

### Testing Instructions

```bash
# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json

# Run task manually (test)
aws ecs run-task \
  --cluster plot-palette-cluster \
  --task-definition plot-palette-worker \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-123],securityGroups=[sg-123],assignPublicIp=ENABLED}" \
  --capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1

# Check task status
aws ecs describe-tasks \
  --cluster plot-palette-cluster \
  --tasks <task-arn>

# View logs
aws logs tail /aws/ecs/plot-palette-worker --follow
```

### Commit Message Template

```
feat(ecs): add task definition and run_task integration

- Create ECS Task Definition for worker container
- Configure Fargate Spot capacity provider
- Set CPU to 0.5 vCPU and memory to 1GB
- Pass environment variables for DynamoDB tables and S3 bucket
- Set stop timeout to 120 seconds for graceful shutdown
- Modify worker to process single job and exit
- Add run_task call to create_job Lambda

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Phase 4 Verification

After completing all tasks, verify the entire phase:

### End-to-End Test

1. **Build and push worker image:**
   ```bash
   ./infrastructure/scripts/build-and-push-worker.sh
   ```

2. **Deploy ECS infrastructure:**
   ```bash
   ./infrastructure/scripts/deploy.sh --region us-east-1 --environment test
   ```

3. **Create test job via API:**
   ```bash
   JOB_ID=$(curl -X POST $API_ENDPOINT/jobs \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "template_id": "tpl-123",
       "seed_data_path": "seed-data/test/data.json",
       "budget_limit": 10.0,
       "output_format": "JSONL",
       "num_records": 100
     }' | jq -r '.job_id')
   ```

4. **Monitor task execution:**
   ```bash
   # Watch logs
   aws logs tail /aws/ecs/plot-palette-worker --follow

   # Check job status
   watch -n 5 "curl -s -H 'Authorization: Bearer $TOKEN' $API_ENDPOINT/jobs/$JOB_ID | jq '.status'"

   # Monitor dashboard
   curl -H "Authorization: Bearer $TOKEN" $API_ENDPOINT/dashboard/$JOB_ID | jq
   ```

5. **Verify outputs:**
   ```bash
   # Check S3 for batch files
   aws s3 ls s3://$BUCKET_NAME/jobs/$JOB_ID/outputs/

   # Check exports
   aws s3 ls s3://$BUCKET_NAME/jobs/$JOB_ID/exports/

   # Download and verify
   aws s3 cp s3://$BUCKET_NAME/jobs/$JOB_ID/exports/dataset.jsonl .
   wc -l dataset.jsonl  # Should be 100
   ```

6. **Test Spot interruption (manual):**
   - Simulate SIGTERM: `docker kill --signal=TERM <container-id>`
   - Verify checkpoint saved
   - Restart task, verify resume from checkpoint

### Success Criteria

- [ ] Worker container builds successfully
- [ ] Worker pushed to ECR
- [ ] ECS task definition registered
- [ ] Task starts via run_task API
- [ ] Worker pulls job from queue
- [ ] Worker generates data using Bedrock
- [ ] Checkpoints saved to S3 with ETags
- [ ] Cost tracking written to DynamoDB
- [ ] Budget enforcement stops job at limit
- [ ] Exports created in all formats (JSONL, Parquet, CSV)
- [ ] Worker handles SIGTERM gracefully
- [ ] Job resumes from checkpoint after interruption
- [ ] Job marked COMPLETED when done
- [ ] CloudWatch logs capture all output

### Estimated Total Cost (1 job, 100 records, ~10 minutes)

- Fargate Spot (0.5 vCPU, 1GB, 10 min): ~$0.002
- Bedrock (estimate 200K tokens): ~$0.12
- S3 (batch uploads + exports): ~$0.001
- DynamoDB (writes): ~$0.001
- **Total: ~$0.124 per job**

---

## Known Limitations & Technical Debt

1. **Single Job per Task:** Each task processes one job then exits (could optimize to process multiple jobs)
2. **Fixed Task Size:** CPU/memory not configurable per job (could parameterize in job config)
3. **No Auto-scaling:** Tasks started one per job (could implement ECS Service with auto-scaling based on queue depth)
4. **Simplified Token Counting:** Rough estimation (could integrate actual tokenizer)
5. **No Model Fallback:** If Bedrock model unavailable, job fails (could retry with different model)

---

## Next Steps

With the generation workers complete, you're ready to proceed to **Phase 5: Prompt Template Engine**.

Phase 5 will add:
- Advanced template features (loops, conditionals, filters)
- Custom Jinja2 filters for LLM operations
- Template validation and testing UI components
- Sample template library
- Template import/export functionality

---

**Navigation:**
- [← Back to README](./README.md)
- [← Previous: Phase 3](./Phase-3.md)
- [Next: Phase 5 - Prompt Template Engine →](./Phase-5.md)
