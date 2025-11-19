# Plot Palette - Deployment Troubleshooting Guide

Common deployment issues and their solutions.

## Table of Contents

- [CloudFormation Issues](#cloudformation-issues)
- [Bedrock Access Issues](#bedrock-access-issues)
- [Network and VPC Issues](#network-and-vpc-issues)
- [DynamoDB Issues](#dynamodb-issues)
- [Lambda Function Issues](#lambda-function-issues)
- [ECS Fargate Issues](#ecs-fargate-issues)
- [Amplify Frontend Issues](#amplify-frontend-issues)
- [Authentication Issues](#authentication-issues)
- [General Debugging](#general-debugging)

---

## CloudFormation Issues

### Issue: Stack creation fails with "Template too large"

**Error Message:**
```
Template format error: Template size (XXXXXX bytes) exceeds maximum allowed size (51200 bytes)
```

**Cause:** Master template exceeds CloudFormation's 51,200 byte limit for direct uploads.

**Solution:**
Templates must be uploaded to S3 first:

```bash
# Upload templates
./infrastructure/scripts/upload-templates.sh us-east-1

# Ensure TemplateURL uses S3, not local file
# Master stack automatically uses S3 URLs for nested stacks
```

**Verification:**
```bash
# Check template is in S3
aws s3 ls s3://plot-palette-cfn-{account-id}-{region}/
```

---

### Issue: Nested stack creation fails

**Error Message:**
```
Embedded stack arn:aws:cloudformation... was not successfully created:
The following resource(s) failed to create: [ResourceName].
```

**Cause:** Nested stack template has errors or missing dependencies.

**Solution:**

1. Check nested stack events:
```bash
# Get nested stack ID from master stack resources
aws cloudformation describe-stack-resources \
    --stack-name plot-palette \
    --region us-east-1

# Get events from failing nested stack
aws cloudformation describe-stack-events \
    --stack-name <nested-stack-name> \
    --region us-east-1 \
    --max-items 20
```

2. Validate individual template:
```bash
aws cloudformation validate-template \
    --template-body file://infrastructure/cloudformation/database-stack.yaml \
    --region us-east-1
```

3. Fix the nested template and re-upload:
```bash
./infrastructure/scripts/upload-templates.sh us-east-1
```

---

### Issue: Stack update fails, stuck in UPDATE_ROLLBACK_FAILED

**Symptoms:** Stack can't roll back automatically.

**Solution:**

```bash
# Continue rollback, skipping failed resources
aws cloudformation continue-update-rollback \
    --stack-name plot-palette \
    --region us-east-1 \
    --resources-to-skip <ResourceLogicalId>

# Or use rollback script
./infrastructure/scripts/rollback-stack.sh plot-palette us-east-1
```

**Alternative:** Delete and recreate stack (if data loss acceptable):
```bash
# Backup DynamoDB first!
./infrastructure/scripts/backup-dynamodb.sh plot-palette us-east-1

# Delete stack
./infrastructure/scripts/deploy-nested.sh --delete --stack-name plot-palette
```

---

### Issue: DynamoDB table already exists

**Error Message:**
```
Table already exists: plot-palette-jobs-production
```

**Cause:** Previous deployment not fully cleaned up.

**Solution:**

Option 1: Delete existing tables manually:
```bash
aws dynamodb delete-table --table-name plot-palette-jobs-production --region us-east-1
aws dynamodb delete-table --table-name plot-palette-queue-production --region us-east-1
# Repeat for all tables
```

Option 2: Use different environment name:
```bash
# Edit parameter file
vim infrastructure/parameters/production.json
# Change EnvironmentName to "production2"

# Deploy with new environment
./infrastructure/scripts/deploy-nested.sh --create --environment production2
```

---

## Bedrock Access Issues

### Issue: Bedrock access denied

**Error Message:**
```
AccessDeniedException: You don't have access to the model with the specified model ID.
```

**Cause:** Bedrock model access not enabled for your account.

**Solution:**

1. Go to Bedrock console:
   ```
   https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
   ```

2. Request access for models:
   - Anthropic Claude (all versions)
   - Meta Llama 3.1 (8B and 70B)
   - Mistral 7B

3. Wait for approval (usually instant for Claude and Llama)

4. Verify access:
   ```bash
   aws bedrock list-foundation-models --region us-east-1
   ```

**Note:** Model availability varies by region. Use us-east-1 for broadest support.

---

### Issue: Bedrock not available in region

**Error Message:**
```
Could not connect to the endpoint URL: "https://bedrock.eu-west-3.amazonaws.com/"
```

**Cause:** Bedrock service not available in selected region.

**Solution:**

Use a Bedrock-supported region:
- us-east-1 (N. Virginia) - **Recommended**
- us-west-2 (Oregon)
- eu-west-1 (Ireland)

```bash
# Check regions.json for availability
cat infrastructure/parameters/regions.json

# Redeploy to supported region
./infrastructure/scripts/deploy-nested.sh --create --region us-east-1
```

---

## Network and VPC Issues

### Issue: VPC quota exceeded

**Error Message:**
```
The maximum number of VPCs has been reached.
```

**Cause:** AWS account limit (default: 5 VPCs per region).

**Solution:**

Option 1: Delete unused VPCs:
```bash
# List VPCs
aws ec2 describe-vpcs --region us-east-1

# Delete unused VPC
aws ec2 delete-vpc --vpc-id vpc-xxxxx --region us-east-1
```

Option 2: Request quota increase:
- Go to AWS Service Quotas console
- Request increase for "VPCs per Region"

Option 3: Deploy to different region:
```bash
./infrastructure/scripts/deploy-nested.sh --create --region us-west-2
```

---

### Issue: Subnet IP exhaustion

**Symptoms:** ECS tasks fail to start with "no available IPs" error.

**Cause:** Subnets are /24 (254 usable IPs), may be exhausted.

**Solution:**

Check subnet usage:
```bash
aws ec2 describe-subnets --region us-east-1 \
    --filters "Name=vpc-id,Values=<vpc-id>" \
    --query 'Subnets[].{ID:SubnetId,Available:AvailableIpAddressCount}'
```

If exhausted, increase CIDR range in network-stack.yaml:
```yaml
# Change from /24 to /23 (512 IPs)
PublicSubnetA:
  Type: AWS::EC2::Subnet
  Properties:
    CidrBlock: 10.0.1.0/23  # Was 10.0.1.0/24
```

---

## DynamoDB Issues

### Issue: Table creation fails with "Table name already exists"

**Cause:** Table from previous deployment still exists.

**Solution:**

```bash
# List existing tables
aws dynamodb list-tables --region us-east-1 | grep plot-palette

# Delete table (WARNING: data loss!)
aws dynamodb delete-table --table-name <table-name> --region us-east-1

# Or restore from backup later
./infrastructure/scripts/backup-dynamodb.sh plot-palette us-east-1
```

---

### Issue: Provisioned throughput exceeded

**Error Message:**
```
ProvisionedThroughputExceededException: Rate exceeded for table
```

**Cause:** DynamoDB on-demand mode should prevent this, but spiky traffic can cause brief throttling.

**Solution:**

Tables use on-demand mode by default (no limit). If seeing this error:

1. Check table configuration:
```bash
aws dynamodb describe-table \
    --table-name plot-palette-jobs-production \
    --region us-east-1 \
    --query 'Table.BillingModeSummary'
```

2. Ensure on-demand mode:
```yaml
# In database-stack.yaml
BillingMode: PAY_PER_REQUEST  # Should be set
```

3. If persistent, implement exponential backoff in application code.

---

## Lambda Function Issues

### Issue: Lambda function timeout

**Error Message:**
```
Task timed out after 30.00 seconds
```

**Cause:** Lambda execution exceeded configured timeout.

**Solution:**

1. Increase timeout in api-stack.yaml:
```yaml
Timeout: 60  # Increase from 30 to 60 seconds
```

2. Optimize function code to reduce execution time

3. Check CloudWatch logs for bottlenecks:
```bash
aws logs tail /aws/lambda/plot-palette-api-JobsFunction --follow
```

---

### Issue: Lambda cold start issues

**Symptoms:** First request after idle period is slow.

**Cause:** Lambda cold starts (normal behavior).

**Solution:**

1. Implement provisioned concurrency (costs more):
```yaml
ProvisionedConcurrencyConfig:
  ProvisionedConcurrentExecutions: 1
```

2. Or optimize cold start:
   - Reduce package size
   - Use Lambda layers for dependencies
   - Minimize imports

---

## ECS Fargate Issues

### Issue: ECS tasks fail to start

**Error:** "CannotPullContainerError"

**Cause:** Container image not found or IAM permissions missing.

**Solution:**

1. Verify ECR image exists:
```bash
aws ecr describe-images \
    --repository-name plot-palette-worker \
    --region us-east-1
```

2. Check ECS task execution role has ECR permissions:
```bash
aws iam get-role-policy \
    --role-name plot-palette-ecs-task-role \
    --policy-name ECRAccessPolicy
```

3. Build and push image:
```bash
./infrastructure/scripts/build-and-push-worker.sh
```

---

### Issue: Fargate Spot interruptions too frequent

**Symptoms:** Jobs frequently interrupted and restarted.

**Cause:** High Spot instance reclamation in region.

**Solution:**

1. Check Fargate Spot availability in region

2. Switch to On-Demand Fargate (more expensive):
```yaml
# In compute-stack.yaml, change capacity provider
CapacityProviderStrategy:
  - CapacityProvider: FARGATE  # Was FARGATE_SPOT
    Weight: 1
```

3. Or deploy to different region with better Spot availability

---

## Amplify Frontend Issues

### Issue: Amplify build fails

**Error:** "Build failed" in Amplify console.

**Cause:** NPM dependencies or build script issues.

**Solution:**

1. Check Amplify build logs:
   - Go to Amplify console
   - Select app
   - Click on failed build
   - View logs

2. Common fixes:
   - Update build settings in `frontend-stack.yaml`
   - Ensure `package.json` scripts are correct
   - Check environment variables are set

3. Test build locally:
```bash
cd frontend
npm install
npm run build
```

---

### Issue: Amplify app not accessible

**Symptoms:** Frontend URL returns 404 or connection error.

**Cause:** Deployment not complete or DNS propagation delay.

**Solution:**

1. Check deployment status:
```bash
aws amplify list-apps --region us-east-1
```

2. Trigger manual deployment:
```bash
aws amplify start-job \
    --app-id <app-id> \
    --branch-name main \
    --job-type RELEASE \
    --region us-east-1
```

3. Wait 2-5 minutes for DNS propagation

---

## Authentication Issues

### Issue: Cognito user signup fails

**Error:** "InvalidPasswordException"

**Cause:** Password doesn't meet policy requirements.

**Solution:**

Password must have:
- Minimum 12 characters
- Uppercase letter
- Lowercase letter
- Number
- Special character

```bash
# Valid password example
aws cognito-idp sign-up \
    --client-id <client-id> \
    --username user@example.com \
    --password "MySecure123!@#" \
    --region us-east-1
```

---

### Issue: API returns 401 Unauthorized

**Cause:** JWT token expired or invalid.

**Solution:**

1. Get new token:
```bash
aws cognito-idp initiate-auth \
    --client-id <client-id> \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME=user@example.com,PASSWORD=<password> \
    --region us-east-1
```

2. Use `AccessToken` from response in API requests:
```bash
curl -H "Authorization: Bearer <AccessToken>" \
    https://api-endpoint.execute-api.us-east-1.amazonaws.com/jobs
```

3. Implement token refresh logic in frontend

---

## General Debugging

### Enable Debug Logging

```bash
# Set verbose output
export AWS_DEBUG=true

# CloudFormation events
aws cloudformation describe-stack-events \
    --stack-name plot-palette \
    --region us-east-1 \
    --max-items 50

# Lambda logs
aws logs tail /aws/lambda/plot-palette-api-JobsFunction \
    --follow \
    --format short
```

### Check Resource Limits

```bash
# Service quotas
aws service-quotas list-service-quotas \
    --service-code ec2 \
    --region us-east-1

# Current usage
aws cloudformation describe-account-limits --region us-east-1
```

### Validate Templates Locally

```bash
# Validate all templates
for template in infrastructure/cloudformation/*.yaml; do
    echo "Validating $template..."
    aws cloudformation validate-template \
        --template-body "file://$template" \
        --region us-east-1
done
```

---

## Getting Help

If issues persist:

1. **Check CloudFormation Events:**
   ```bash
   aws cloudformation describe-stack-events \
       --stack-name plot-palette \
       --region us-east-1
   ```

2. **Review CloudWatch Logs:**
   - Lambda logs: `/aws/lambda/plot-palette-*`
   - ECS logs: `/ecs/plot-palette-*`

3. **AWS Support:**
   - Open case in AWS Support Console
   - Include stack name, region, error messages

4. **Community:**
   - GitHub Issues: https://github.com/your-repo/plot-palette/issues
   - Check existing issues for solutions

---

## Disaster Recovery

See [Disaster Recovery Guide](./disaster-recovery.md) for:
- Backup procedures
- Restore from backup
- Multi-region failover
- RTO/RPO targets
