# Plot Palette - Deployment Guide

Complete guide for deploying Plot Palette to AWS using CloudFormation nested stacks.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (5 minutes)](#quick-start-5-minutes)
- [Detailed Deployment](#detailed-deployment)
- [Environment-Specific Deployment](#environment-specific-deployment)
- [Multi-Region Deployment](#multi-region-deployment)
- [Post-Deployment Validation](#post-deployment-validation)
- [Updating the Stack](#updating-the-stack)
- [Rollback and Recovery](#rollback-and-recovery)
- [Cleanup](#cleanup)

---

## Prerequisites

### Required Tools

- **AWS Account** with Administrator or PowerUser permissions
- **AWS CLI** v2+ configured with credentials
  ```bash
  aws --version  # Should be 2.x or higher
  aws sts get-caller-identity  # Verify credentials
  ```
- **jq** - JSON processor
  ```bash
  # macOS
  brew install jq

  # Linux
  sudo apt-get install jq  # Debian/Ubuntu
  sudo yum install jq      # RedHat/CentOS
  ```
- **Git** - Version control
- **Bash** - Shell environment (Linux/macOS/WSL)

### AWS Service Quotas

Verify you have sufficient quotas:

1. **AWS Bedrock Access** (Critical)
   - Navigate to: https://console.aws.amazon.com/bedrock/
   - Enable model access for:
     - Anthropic Claude (recommended)
     - Meta Llama 3.1 (8B and 70B)
     - Mistral 7B (optional)

2. **ECS Fargate** - Check Fargate Spot capacity available
3. **Cognito User Pools** - User pool quota available
4. **S3 Buckets** - Can create new buckets

### Knowledge Prerequisites

Familiarity with:
- AWS CloudFormation basics
- AWS Console navigation
- Command-line operations
- Basic AWS services (S3, Lambda, API Gateway)

---

## Quick Start (5 minutes)

For a production deployment in us-east-1:

```bash
# 1. Clone repository
git clone <repository-url>
cd plot-palette

# 2. Configure AWS credentials (if not already done)
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Default region (us-east-1)

# 3. Validate parameters
./infrastructure/scripts/validate-parameters.sh production

# 4. Deploy!
./infrastructure/scripts/deploy-nested.sh \
    --create \
    --environment production \
    --region us-east-1
```

**Deployment time:** 15-20 minutes

After deployment completes, you'll see output with:
- Frontend URL (Amplify web app)
- API Endpoint
- Cognito User Pool details

**Access the application:** Open the Frontend URL in your browser.

---

## Detailed Deployment

### Step 1: Validate Prerequisites

```bash
# Check AWS CLI
aws --version

# Verify credentials
aws sts get-caller-identity

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1

# Check jq
jq --version
```

### Step 2: Review and Customize Parameters

Edit environment-specific parameter files:

```bash
# Production
vim infrastructure/parameters/production.json

# Staging
vim infrastructure/parameters/staging.json

# Development
vim infrastructure/parameters/development.json
```

**Key parameters to customize:**

- `AdminEmail` - Your email for admin user and notifications
- `InitialBudgetLimit` - Default job budget (USD)
- `LogRetentionDays` - CloudWatch log retention

See [Parameter Reference](./parameter-reference.md) for complete details.

### Step 3: Validate Parameters

```bash
# Validate production parameters
./infrastructure/scripts/validate-parameters.sh production

# Validate staging
./infrastructure/scripts/validate-parameters.sh staging
```

This checks:
- JSON syntax
- Email format
- Budget limits
- AWS credentials
- Bedrock availability

### Step 4: Estimate Costs

```bash
# Estimate monthly costs for production
./infrastructure/scripts/estimate-cost.sh production

# Estimate for development
./infrastructure/scripts/estimate-cost.sh development
```

Review the cost breakdown before proceeding.

### Step 5: Upload Templates

```bash
# Upload CloudFormation templates to S3
./infrastructure/scripts/upload-templates.sh us-east-1
```

This creates an S3 bucket: `plot-palette-cfn-{account-id}-{region}`

### Step 6: Deploy Master Stack

```bash
# Create new stack
./infrastructure/scripts/deploy-nested.sh \
    --create \
    --stack-name plot-palette \
    --environment production \
    --region us-east-1
```

**What happens:**
1. Parameters validated
2. Templates uploaded to S3
3. Master stack created
4. Nested stacks deployed in order:
   - Network (VPC, subnets, security groups)
   - Storage (S3 buckets)
   - Database (DynamoDB tables)
   - IAM (Roles and policies)
   - Auth (Cognito User Pool)
   - API (HTTP API Gateway + Lambda)
   - Compute (ECS Fargate cluster)
   - Frontend (Amplify hosting)
5. Stack outputs displayed

**Expected duration:** 15-20 minutes

### Step 7: Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].StackStatus'

# Get outputs
aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].Outputs'
```

See [Post-Deployment Validation](#post-deployment-validation) for detailed testing.

---

## Environment-Specific Deployment

### Development Environment

Optimized for cost and speed:

```bash
./infrastructure/scripts/deploy-nested.sh \
    --create \
    --stack-name plot-palette-dev \
    --environment development \
    --region us-east-1
```

**Characteristics:**
- Budget limit: $10
- Log retention: 1 day
- Minimal resources

### Staging Environment

Pre-production testing:

```bash
./infrastructure/scripts/deploy-nested.sh \
    --create \
    --stack-name plot-palette-staging \
    --environment staging \
    --region us-east-1
```

**Characteristics:**
- Budget limit: $50
- Log retention: 7 days
- Production-like configuration

### Production Environment

Full production deployment:

```bash
./infrastructure/scripts/deploy-nested.sh \
    --create \
    --stack-name plot-palette \
    --environment production \
    --region us-east-1
```

**Characteristics:**
- Budget limit: $100
- Log retention: 30 days
- Optimized for reliability

---

## Multi-Region Deployment

Deploy to multiple regions for:
- Geographic redundancy
- Lower latency for global users
- Bedrock model availability

### Recommended Regions

1. **us-east-1** (N. Virginia) - Broadest Bedrock model availability
2. **us-west-2** (Oregon) - Good Bedrock availability, West Coast latency
3. **eu-west-1** (Ireland) - European data residency

### Deploy to Multiple Regions

```bash
# Sequential deployment (recommended)
./infrastructure/scripts/deploy-multi-region.sh \
    --regions us-east-1,us-west-2,eu-west-1 \
    --environment production

# Parallel deployment (experimental)
./infrastructure/scripts/deploy-multi-region.sh \
    --regions us-east-1,us-west-2 \
    --environment production \
    --parallel
```

**Note:** Each region creates an independent stack with separate resources.

---

## Post-Deployment Validation

### 1. Access Frontend

```bash
# Get frontend URL
FRONTEND_URL=$(aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text)

echo "Frontend: $FRONTEND_URL"

# Open in browser
open $FRONTEND_URL  # macOS
# or
xdg-open $FRONTEND_URL  # Linux
```

### 2. Create Test User

```bash
# Get Cognito details
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

# Create user
aws cognito-idp sign-up \
    --client-id $CLIENT_ID \
    --username test@example.com \
    --password TestPassword123! \
    --region us-east-1

# Confirm user (admin action)
aws cognito-idp admin-confirm-sign-up \
    --user-pool-id $USER_POOL_ID \
    --username test@example.com \
    --region us-east-1
```

### 3. Test API Health Endpoint

```bash
# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

# Test health endpoint
curl ${API_ENDPOINT}/health
```

Expected response: `{"status": "healthy"}`

### 4. Verify Resources

```bash
# Check ECS cluster
aws ecs describe-clusters \
    --clusters plot-palette-production \
    --region us-east-1

# Check DynamoDB tables
aws dynamodb list-tables --region us-east-1 | grep plot-palette

# Check S3 buckets
aws s3 ls | grep plot-palette
```

---

## Updating the Stack

### Safe Update Process

Always use change sets to preview changes before applying:

```bash
# Update with change set review
./infrastructure/scripts/update-stack.sh \
    plot-palette \
    production \
    us-east-1
```

**What happens:**
1. Templates re-uploaded
2. Change set created
3. Changes displayed in table format
4. Prompt for confirmation
5. If DynamoDB tables affected, backup prompt
6. Change set executed
7. Stack update waits for completion

### Manual Update Steps

```bash
# 1. Upload new templates
./infrastructure/scripts/upload-templates.sh us-east-1

# 2. Create change set
aws cloudformation create-change-set \
    --stack-name plot-palette \
    --change-set-name update-$(date +%Y%m%d-%H%M%S) \
    --template-body file://infrastructure/cloudformation/master-stack.yaml \
    --parameters file://infrastructure/parameters/production.json \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --region us-east-1

# 3. Review change set
aws cloudformation describe-change-set \
    --stack-name plot-palette \
    --change-set-name <change-set-name> \
    --region us-east-1

# 4. Execute if satisfied
aws cloudformation execute-change-set \
    --stack-name plot-palette \
    --change-set-name <change-set-name> \
    --region us-east-1
```

### Backup Before Update

If DynamoDB tables will be replaced:

```bash
# Backup all tables
./infrastructure/scripts/backup-dynamodb.sh plot-palette us-east-1
```

---

## Rollback and Recovery

### Automatic Rollback

CloudFormation automatically rolls back on update failures.

### Manual Rollback

```bash
# Rollback failed update
./infrastructure/scripts/rollback-stack.sh plot-palette us-east-1
```

### Restore from Backup

```bash
# List DynamoDB backups
aws dynamodb list-backups \
    --table-name <table-name> \
    --region us-east-1

# Restore table
aws dynamodb restore-table-from-backup \
    --target-table-name <new-table-name> \
    --backup-arn <backup-arn> \
    --region us-east-1
```

---

## Cleanup

### Delete Stack

```bash
# Using deployment script
./infrastructure/scripts/deploy-nested.sh \
    --delete \
    --stack-name plot-palette \
    --region us-east-1

# Or manually
aws cloudformation delete-stack \
    --stack-name plot-palette \
    --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --stack-name plot-palette \
    --region us-east-1
```

### Manual Cleanup (if needed)

Some resources may need manual deletion:

```bash
# Delete S3 buckets (must be empty first)
aws s3 rm s3://plot-palette-data-<stack-id> --recursive
aws s3 rb s3://plot-palette-data-<stack-id>

# Delete DynamoDB backups
aws dynamodb delete-backup --backup-arn <backup-arn>

# Delete CloudWatch log groups
aws logs delete-log-group --log-group-name /aws/lambda/plot-palette-*
```

---

## Troubleshooting

Common issues and solutions: [Troubleshooting Guide](./troubleshooting.md)

---

## Support

- **Documentation:** [Phase 0 Architecture](../plans/Phase-0.md)
- **Parameter Reference:** [parameter-reference.md](./parameter-reference.md)
- **Troubleshooting:** [troubleshooting.md](./troubleshooting.md)
- **GitHub Issues:** https://github.com/your-repo/plot-palette/issues

---

## Additional Resources

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS Bedrock Model Access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [ECS Fargate Spot](https://docs.aws.amazon.com/AmazonECS/latest/userguide/fargate-capacity-providers.html)
