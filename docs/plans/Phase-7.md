# Phase 7: CloudFormation Nested Stacks

## Phase Goal

Integrate all individual CloudFormation stacks (network, storage, database, auth, API, compute, frontend) into a master nested stack architecture for one-click deployment. By the end of this phase, users can deploy the entire Plot Palette infrastructure with a single CloudFormation command.

**Success Criteria:**
- Master stack template orchestrates all nested stacks
- Parameters passed correctly between stacks
- Stack outputs exported and consumed properly
- Deployment script automates entire process
- Stack update works without data loss
- Rollback works correctly on failure
- Documentation for deployment parameters

**Estimated Tokens:** ~95,000

---

## Prerequisites

- **Phases 1-6** completed (all individual stacks created)
- Understanding of CloudFormation nested stacks
- AWS CLI configured
- S3 bucket for storing templates

---

## Task 1: Master Stack Template

### Goal

Create master CloudFormation template that orchestrates all nested stacks in correct order with proper dependency management.

### Files to Create

- `infrastructure/cloudformation/master-stack.yaml` - Master template
- `infrastructure/scripts/upload-templates.sh` - Upload nested templates to S3

### Prerequisites

- All individual stack templates from Phases 1-6
- AWS account with CloudFormation permissions
- Understanding of stack dependencies

### Implementation Steps

1. **Create master-stack.yaml with all nested stacks:**
   ```yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'Plot Palette - Synthetic Data Generator (Master Stack)'

   Metadata:
     AWS::CloudFormation::Interface:
       ParameterGroups:
         - Label: { default: 'Environment Configuration' }
           Parameters: [EnvironmentName, AdminEmail]
         - Label: { default: 'Default Settings' }
           Parameters: [InitialBudgetLimit, LogRetentionDays]

   Parameters:
     EnvironmentName:
       Type: String
       Default: production
       AllowedValues: [development, staging, production]
       Description: Environment name for resource tagging

     AdminEmail:
       Type: String
       Description: Email for admin user and notifications
       AllowedPattern: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$

     InitialBudgetLimit:
       Type: Number
       Default: 100
       MinValue: 1
       MaxValue: 10000
       Description: Default budget limit for jobs (USD)

     LogRetentionDays:
       Type: Number
       Default: 7
       AllowedValues: [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365]
       Description: CloudWatch Logs retention in days

     TemplatesBucketName:
       Type: String
       Description: S3 bucket containing nested stack templates
       Default: ''

   Conditions:
     CreateTemplatesBucket: !Equals [!Ref TemplatesBucketName, '']

   Resources:
     TemplatesBucket:
       Type: AWS::S3::Bucket
       Condition: CreateTemplatesBucket
       Properties:
         BucketName: !Sub plot-palette-cfn-${AWS::AccountId}-${AWS::Region}
         VersioningConfiguration:
           Status: Enabled
         PublicAccessBlockConfiguration:
           BlockPublicAcls: true
           BlockPublicPolicy: true
           IgnorePublicAcls: true
           RestrictPublicBuckets: true

     NetworkStack:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/network-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           EnvironmentName: !Ref EnvironmentName
         Tags:
           - Key: Component
             Value: Network
           - Key: Environment
             Value: !Ref EnvironmentName

     StorageStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: NetworkStack
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/storage-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           EnvironmentName: !Ref EnvironmentName
         Tags:
           - Key: Component
             Value: Storage

     DatabaseStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: StorageStack
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/database-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           EnvironmentName: !Ref EnvironmentName
         Tags:
           - Key: Component
             Value: Database

     IAMStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [StorageStack, DatabaseStack]
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/iam-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           S3BucketName: !GetAtt StorageStack.Outputs.BucketName
           JobsTableArn: !GetAtt DatabaseStack.Outputs.JobsTableArn
           QueueTableArn: !GetAtt DatabaseStack.Outputs.QueueTableArn
           TemplatesTableArn: !GetAtt DatabaseStack.Outputs.TemplatesTableArn
           CostTrackingTableArn: !GetAtt DatabaseStack.Outputs.CostTrackingTableArn
         Capabilities: [CAPABILITY_IAM]
         Tags:
           - Key: Component
             Value: IAM

     AuthStack:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/auth-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           EnvironmentName: !Ref EnvironmentName
           AdminEmail: !Ref AdminEmail
         Tags:
           - Key: Component
             Value: Authentication

     APIStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [AuthStack, IAMStack]
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/api-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           UserPoolId: !GetAtt AuthStack.Outputs.UserPoolId
           UserPoolClientId: !GetAtt AuthStack.Outputs.UserPoolClientId
           LambdaExecutionRoleArn: !GetAtt IAMStack.Outputs.LambdaExecutionRoleArn
           LogRetentionDays: !Ref LogRetentionDays
         Tags:
           - Key: Component
             Value: API

     ComputeStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [IAMStack, NetworkStack]
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/compute-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           EnvironmentName: !Ref EnvironmentName
           ECSTaskRoleArn: !GetAtt IAMStack.Outputs.ECSTaskRoleArn
           SubnetIds: !GetAtt NetworkStack.Outputs.PublicSubnetIds
           SecurityGroupId: !GetAtt NetworkStack.Outputs.ECSSecurityGroupId
         Tags:
           - Key: Component
             Value: Compute

     FrontendStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [APIStack, AuthStack]
       Properties:
         TemplateURL: !Sub
           - https://${Bucket}.s3.amazonaws.com/frontend-stack.yaml
           - Bucket: !If [CreateTemplatesBucket, !Ref TemplatesBucket, !Ref TemplatesBucketName]
         Parameters:
           ApiEndpoint: !GetAtt APIStack.Outputs.ApiEndpoint
           UserPoolId: !GetAtt AuthStack.Outputs.UserPoolId
           UserPoolClientId: !GetAtt AuthStack.Outputs.UserPoolClientId
           AmplifyServiceRoleArn: !GetAtt IAMStack.Outputs.AmplifyServiceRoleArn
           EnvironmentName: !Ref EnvironmentName
         Tags:
           - Key: Component
             Value: Frontend

   Outputs:
     ApiEndpoint:
       Description: API Gateway endpoint URL
       Value: !GetAtt APIStack.Outputs.ApiEndpoint
       Export:
         Name: !Sub ${AWS::StackName}-ApiEndpoint

     UserPoolId:
       Description: Cognito User Pool ID
       Value: !GetAtt AuthStack.Outputs.UserPoolId
       Export:
         Name: !Sub ${AWS::StackName}-UserPoolId

     UserPoolClientId:
       Description: Cognito User Pool Client ID
       Value: !GetAtt AuthStack.Outputs.UserPoolClientId
       Export:
         Name: !Sub ${AWS::StackName}-UserPoolClientId

     FrontendUrl:
       Description: Amplify frontend URL
       Value: !GetAtt FrontendStack.Outputs.AmplifyAppUrl
       Export:
         Name: !Sub ${AWS::StackName}-FrontendUrl

     BucketName:
       Description: S3 bucket name for data storage
       Value: !GetAtt StorageStack.Outputs.BucketName
       Export:
         Name: !Sub ${AWS::StackName}-BucketName

     ECSClusterName:
       Description: ECS Cluster name
       Value: !GetAtt ComputeStack.Outputs.ClusterName
       Export:
         Name: !Sub ${AWS::StackName}-ECSClusterName
   ```

2. **Create upload-templates.sh script:**
   ```bash
   #!/bin/bash
   set -e

   REGION=${1:-us-east-1}
   AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   BUCKET_NAME="plot-palette-cfn-${AWS_ACCOUNT_ID}-${REGION}"

   echo "Uploading CloudFormation templates to $REGION..."

   # Create templates bucket if doesn't exist
   if ! aws s3 ls s3://$BUCKET_NAME 2>/dev/null; then
       echo "Creating S3 bucket: $BUCKET_NAME"
       if [ "$REGION" = "us-east-1" ]; then
           aws s3 mb s3://$BUCKET_NAME
       else
           aws s3 mb s3://$BUCKET_NAME --region $REGION
       fi

       # Enable versioning
       aws s3api put-bucket-versioning \
           --bucket $BUCKET_NAME \
           --versioning-configuration Status=Enabled

       # Block public access
       aws s3api put-public-access-block \
           --bucket $BUCKET_NAME \
           --public-access-block-configuration \
           "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
   fi

   # Upload all nested templates (exclude master)
   echo "Uploading nested templates..."
   aws s3 sync infrastructure/cloudformation/ s3://$BUCKET_NAME/ \
       --exclude "master-stack.yaml" \
       --exclude "*.pyc" \
       --exclude "__pycache__/*" \
       --region $REGION

   # Validate templates (use local files to avoid S3 bucket policy issues)
   echo "Validating templates..."
   for template in infrastructure/cloudformation/*.yaml; do
       if [ "$(basename $template)" != "master-stack.yaml" ]; then
           echo "  Validating $(basename $template)..."
           aws cloudformation validate-template \
               --template-body "file://$template" \
               --region $REGION > /dev/null
       fi
   done

   echo "✓ Templates uploaded successfully to s3://$BUCKET_NAME/"
   echo "✓ Master stack can now be deployed"
   ```

3. **Make script executable:**
   ```bash
   chmod +x infrastructure/scripts/upload-templates.sh
   ```

### Verification Checklist

- [ ] Master stack template validates successfully
- [ ] All nested stack references correct
- [ ] Parameter passing works between stacks
- [ ] Dependencies properly defined
- [ ] Upload script creates bucket
- [ ] Upload script uploads all templates
- [ ] Template validation passes
- [ ] Outputs exported correctly

### Testing Instructions

```bash
# Upload templates
./infrastructure/scripts/upload-templates.sh us-east-1

# Validate master stack
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/master-stack.yaml

# Test deployment (creates change set only)
aws cloudformation create-change-set \
  --stack-name plot-palette-test \
  --change-set-name initial-deployment \
  --template-body file://infrastructure/cloudformation/master-stack.yaml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=development \
    ParameterKey=AdminEmail,ParameterValue=admin@example.com \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND

# Review change set
aws cloudformation describe-change-set \
  --change-set-name initial-deployment \
  --stack-name plot-palette-test

# Delete change set (don't execute yet)
aws cloudformation delete-change-set \
  --change-set-name initial-deployment \
  --stack-name plot-palette-test
```

### Commit Message Template

```
feat(infrastructure): add master CloudFormation stack with nested stacks

- Create master stack orchestrating 8 nested stacks
- Add dependency management between stacks
- Implement parameter passing via outputs
- Create template upload script with validation
- Enable S3 bucket versioning for templates
- Add comprehensive stack outputs and exports
- Include environment-specific tagging

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~20,000

---

## Task 2: Parameter Management and Validation

### Goal

Create environment-specific parameter files and validation scripts to ensure correct configuration before deployment.

### Files to Create

- `infrastructure/parameters/production.json` - Production parameters
- `infrastructure/parameters/staging.json` - Staging parameters
- `infrastructure/parameters/development.json` - Development parameters
- `infrastructure/scripts/validate-parameters.sh` - Parameter validation script

### Prerequisites

- Task 1 completed (master stack template)
- Understanding of CloudFormation parameter types
- AWS Secrets Manager for sensitive values (optional)

### Implementation Steps

1. **Create production.json (CloudFormation parameter array format):**
   ```json
   [
     {
       "ParameterKey": "EnvironmentName",
       "ParameterValue": "production"
     },
     {
       "ParameterKey": "AdminEmail",
       "ParameterValue": "admin@plotpalette.com"
     },
     {
       "ParameterKey": "InitialBudgetLimit",
       "ParameterValue": "100"
     },
     {
       "ParameterKey": "LogRetentionDays",
       "ParameterValue": "30"
     },
     {
       "ParameterKey": "TemplatesBucketName",
       "ParameterValue": ""
     }
   ]
   ```

2. **Create staging.json:**
   ```json
   [
     {
       "ParameterKey": "EnvironmentName",
       "ParameterValue": "staging"
     },
     {
       "ParameterKey": "AdminEmail",
       "ParameterValue": "staging-admin@plotpalette.com"
     },
     {
       "ParameterKey": "InitialBudgetLimit",
       "ParameterValue": "50"
     },
     {
       "ParameterKey": "LogRetentionDays",
       "ParameterValue": "7"
     },
     {
       "ParameterKey": "TemplatesBucketName",
       "ParameterValue": ""
     }
   ]
   ```

3. **Create development.json:**
   ```json
   [
     {
       "ParameterKey": "EnvironmentName",
       "ParameterValue": "development"
     },
     {
       "ParameterKey": "AdminEmail",
       "ParameterValue": "dev@plotpalette.com"
     },
     {
       "ParameterKey": "InitialBudgetLimit",
       "ParameterValue": "10"
     },
     {
       "ParameterKey": "LogRetentionDays",
       "ParameterValue": "1"
     },
     {
       "ParameterKey": "TemplatesBucketName",
       "ParameterValue": ""
     }
   ]
   ```

4. **Create validate-parameters.sh:**
   ```bash
   #!/bin/bash
   set -e

   ENVIRONMENT=${1:-production}
   PARAM_FILE="infrastructure/parameters/${ENVIRONMENT}.json"

   if [ ! -f "$PARAM_FILE" ]; then
       echo "ERROR: Parameter file not found: $PARAM_FILE"
       exit 1
   fi

   echo "Validating parameters for environment: $ENVIRONMENT"

   # Check JSON syntax
   if ! jq empty "$PARAM_FILE" 2>/dev/null; then
       echo "ERROR: Invalid JSON syntax in $PARAM_FILE"
       exit 1
   fi

   # Extract parameters (from array format)
   ADMIN_EMAIL=$(jq -r '.[] | select(.ParameterKey=="AdminEmail") | .ParameterValue' "$PARAM_FILE")
   BUDGET_LIMIT=$(jq -r '.[] | select(.ParameterKey=="InitialBudgetLimit") | .ParameterValue' "$PARAM_FILE")
   LOG_RETENTION=$(jq -r '.[] | select(.ParameterKey=="LogRetentionDays") | .ParameterValue' "$PARAM_FILE")

   # Validate email format
   if ! echo "$ADMIN_EMAIL" | grep -E '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' > /dev/null; then
       echo "ERROR: Invalid email format: $ADMIN_EMAIL"
       exit 1
   fi

   # Validate budget limit
   if [ "$BUDGET_LIMIT" -lt 1 ] || [ "$BUDGET_LIMIT" -gt 10000 ]; then
       echo "ERROR: InitialBudgetLimit must be between 1 and 10000, got: $BUDGET_LIMIT"
       exit 1
   fi

   # Validate log retention
   VALID_RETENTION="1 3 5 7 14 30 60 90 120 150 180 365"
   if ! echo "$VALID_RETENTION" | grep -w "$LOG_RETENTION" > /dev/null; then
       echo "ERROR: Invalid LogRetentionDays: $LOG_RETENTION"
       echo "Valid values: $VALID_RETENTION"
       exit 1
   fi

   # Check AWS account is configured
   if ! aws sts get-caller-identity > /dev/null 2>&1; then
       echo "ERROR: AWS CLI not configured or credentials invalid"
       exit 1
   fi

   # Check Bedrock access (if available)
   echo "Checking Bedrock model access..."
   REGION=$(aws configure get region || echo "us-east-1")
   if aws bedrock list-foundation-models --region $REGION > /dev/null 2>&1; then
       MODELS=$(aws bedrock list-foundation-models --region $REGION --query 'modelSummaries[].modelId' --output text)

       # Check for required models
       REQUIRED_MODELS="anthropic.claude-v2 meta.llama3-1-8b meta.llama3-1-70b"
       for model in $REQUIRED_MODELS; do
           if ! echo "$MODELS" | grep -q "$model"; then
               echo "WARNING: Bedrock model $model not available in $REGION"
               echo "Enable model access in AWS Bedrock console before deployment"
           fi
       done
   else
       echo "WARNING: Cannot check Bedrock access (service may not be available in region)"
   fi

   echo "✓ Parameter validation passed"
   echo
   echo "Deployment command:"
   echo "  ./infrastructure/scripts/deploy.sh --environment $ENVIRONMENT --region $REGION"
   ```

5. **Make script executable:**
   ```bash
   chmod +x infrastructure/scripts/validate-parameters.sh
   ```

6. **Document parameter reference** (`docs/deployment/parameter-reference.md`):
   ```markdown
   # CloudFormation Parameter Reference

   ## Required Parameters

   ### EnvironmentName
   - **Type:** String
   - **Allowed Values:** development, staging, production
   - **Description:** Environment name for resource tagging and naming
   - **Example:** `production`

   ### AdminEmail
   - **Type:** String
   - **Pattern:** Valid email address
   - **Description:** Email for initial admin user and system notifications
   - **Example:** `admin@example.com`

   ## Optional Parameters

   ### InitialBudgetLimit
   - **Type:** Number
   - **Range:** 1 - 10000
   - **Default:** 100
   - **Description:** Default budget limit for generation jobs in USD
   - **Example:** `50`

   ### LogRetentionDays
   - **Type:** Number
   - **Allowed Values:** 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365
   - **Default:** 7
   - **Description:** CloudWatch Logs retention period
   - **Example:** `30`

   ### TemplatesBucketName
   - **Type:** String
   - **Default:** (creates new bucket)
   - **Description:** Existing S3 bucket for CloudFormation templates
   - **Example:** `my-cfn-templates-bucket`

   ## Environment-Specific Recommendations

   ### Development
   - LogRetentionDays: 1
   - InitialBudgetLimit: 10
   - Purpose: Quick iteration, minimal costs

   ### Staging
   - LogRetentionDays: 7
   - InitialBudgetLimit: 50
   - Purpose: Pre-production testing

   ### Production
   - LogRetentionDays: 30
   - InitialBudgetLimit: 100
   - Purpose: Production workloads, compliance
   ```

### Verification Checklist

- [ ] Parameter files exist for all three environments
- [ ] JSON syntax is valid in all parameter files
- [ ] Validation script checks email format
- [ ] Validation script checks budget limits
- [ ] Validation script checks log retention values
- [ ] Validation script verifies AWS credentials
- [ ] Validation script checks Bedrock access
- [ ] Parameter reference documentation complete

### Testing Instructions

```bash
# Validate production parameters
./infrastructure/scripts/validate-parameters.sh production

# Validate staging parameters
./infrastructure/scripts/validate-parameters.sh staging

# Test with invalid email (should fail)
echo '{"Parameters":{"AdminEmail":"invalid-email"}}' > /tmp/test.json
./infrastructure/scripts/validate-parameters.sh /tmp/test.json

# Test missing file (should fail)
./infrastructure/scripts/validate-parameters.sh nonexistent

# Check JSON syntax
jq empty infrastructure/parameters/production.json
```

### Commit Message Template

```
feat(infrastructure): add parameter management for multi-environment deployment

- Create environment-specific parameter files (dev, staging, prod)
- Add validation script with email, budget, and retention checks
- Validate AWS credentials and Bedrock access
- Check CloudFormation parameter constraints
- Add parameter reference documentation
- Include environment-specific recommendations

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 3: Stack Update Strategy with Change Sets

### Goal

Implement safe stack update process using CloudFormation change sets with backup and rollback capabilities.

### Files to Create

- `infrastructure/scripts/update-stack.sh` - Stack update script
- `infrastructure/scripts/backup-dynamodb.sh` - DynamoDB backup script
- `infrastructure/scripts/rollback-stack.sh` - Rollback automation

### Prerequisites

- Task 1 completed (master stack deployed)
- Understanding of CloudFormation change sets
- DynamoDB backup/restore knowledge

### Implementation Steps

1. **Create update-stack.sh:**
   ```bash
   #!/bin/bash
   set -e

   STACK_NAME=${1:-plot-palette}
   ENVIRONMENT=${2:-production}
   REGION=${3:-us-east-1}

   echo "=== Stack Update Process ==="
   echo "Stack: $STACK_NAME"
   echo "Environment: $ENVIRONMENT"
   echo "Region: $REGION"
   echo

   # Validate parameters
   ./infrastructure/scripts/validate-parameters.sh $ENVIRONMENT

   # Upload latest templates
   ./infrastructure/scripts/upload-templates.sh $REGION

   # Create change set
   CHANGE_SET_NAME="update-$(date +%Y%m%d-%H%M%S)"
   echo "Creating change set: $CHANGE_SET_NAME"

   aws cloudformation create-change-set \
       --stack-name $STACK_NAME \
       --change-set-name $CHANGE_SET_NAME \
       --template-body file://infrastructure/cloudformation/master-stack.yaml \
       --parameters file://infrastructure/parameters/${ENVIRONMENT}.json \
       --tags Key=Environment,Value=${ENVIRONMENT} Key=Project,Value=plot-palette Key=ManagedBy,Value=cloudformation \
       --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
       --region $REGION

   echo "Waiting for change set creation..."
   aws cloudformation wait change-set-create-complete \
       --change-set-name $CHANGE_SET_NAME \
       --stack-name $STACK_NAME \
       --region $REGION

   # Display changes
   echo
   echo "=== Proposed Changes ==="
   aws cloudformation describe-change-set \
       --change-set-name $CHANGE_SET_NAME \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'Changes[].{Action:ResourceChange.Action,Resource:ResourceChange.LogicalResourceId,Type:ResourceChange.ResourceType,Replacement:ResourceChange.Replacement}' \
       --output table

   # Check for data-impacting changes
   CRITICAL_CHANGES=$(aws cloudformation describe-change-set \
       --change-set-name $CHANGE_SET_NAME \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'Changes[?ResourceChange.ResourceType==`AWS::DynamoDB::Table` && ResourceChange.Replacement==`True`].ResourceChange.LogicalResourceId' \
       --output text)

   if [ -n "$CRITICAL_CHANGES" ]; then
       echo
       echo "⚠️  WARNING: The following DynamoDB tables will be replaced:"
       echo "$CRITICAL_CHANGES"
       echo
       echo "This will result in DATA LOSS unless backed up!"
       echo
       read -p "Do you want to backup DynamoDB tables first? (y/n) " -n 1 -r
       echo
       if [[ $REPLY =~ ^[Yy]$ ]]; then
           ./infrastructure/scripts/backup-dynamodb.sh $STACK_NAME $REGION
       fi
   fi

   # Confirm execution
   echo
   read -p "Execute this change set? (y/n) " -n 1 -r
   echo
   if [[ ! $REPLY =~ ^[Yy]$ ]]; then
       echo "Aborting. Change set not executed."
       echo "To delete the change set:"
       echo "  aws cloudformation delete-change-set --change-set-name $CHANGE_SET_NAME --stack-name $STACK_NAME"
       exit 1
   fi

   # Execute change set
   echo "Executing change set..."
   aws cloudformation execute-change-set \
       --change-set-name $CHANGE_SET_NAME \
       --stack-name $STACK_NAME \
       --region $REGION

   echo "Waiting for stack update to complete..."
   aws cloudformation wait stack-update-complete \
       --stack-name $STACK_NAME \
       --region $REGION || {
       echo "ERROR: Stack update failed!"
       echo "Check CloudFormation console for details."
       echo "To rollback:"
       echo "  ./infrastructure/scripts/rollback-stack.sh $STACK_NAME $REGION"
       exit 1
   }

   echo
   echo "✓ Stack update completed successfully"
   echo
   echo "Updated outputs:"
   aws cloudformation describe-stacks \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'Stacks[0].Outputs' \
       --output table
   ```

2. **Create backup-dynamodb.sh:**
   ```bash
   #!/bin/bash
   set -e

   STACK_NAME=${1:-plot-palette}
   REGION=${2:-us-east-1}
   BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"

   echo "=== DynamoDB Backup Process ==="
   echo "Stack: $STACK_NAME"
   echo "Region: $REGION"
   echo "Backup name: $BACKUP_NAME"
   echo

   # Get table names from stack
   TABLES=$(aws cloudformation describe-stack-resources \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'StackResources[?ResourceType==`AWS::DynamoDB::Table`].PhysicalResourceId' \
       --output text)

   if [ -z "$TABLES" ]; then
       echo "No DynamoDB tables found in stack"
       exit 0
   fi

   echo "Backing up tables:"
   for TABLE in $TABLES; do
       echo "  - $TABLE"

       # Create on-demand backup
       aws dynamodb create-backup \
           --table-name $TABLE \
           --backup-name "${BACKUP_NAME}-${TABLE}" \
           --region $REGION

       echo "    ✓ Backup created: ${BACKUP_NAME}-${TABLE}"
   done

   echo
   echo "✓ All DynamoDB tables backed up successfully"
   echo
   echo "To restore a backup:"
   echo "  aws dynamodb restore-table-from-backup \\"
   echo "    --target-table-name <new-table-name> \\"
   echo "    --backup-arn <backup-arn> \\"
   echo "    --region $REGION"
   echo
   echo "List backups:"
   echo "  aws dynamodb list-backups --table-name <table-name> --region $REGION"
   ```

3. **Create rollback-stack.sh:**
   ```bash
   #!/bin/bash
   set -e

   STACK_NAME=${1:-plot-palette}
   REGION=${2:-us-east-1}

   echo "=== Stack Rollback Process ==="
   echo "Stack: $STACK_NAME"
   echo "Region: $REGION"
   echo

   # Check stack status
   STATUS=$(aws cloudformation describe-stacks \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'Stacks[0].StackStatus' \
       --output text 2>/dev/null || echo "NOT_FOUND")

   if [ "$STATUS" = "NOT_FOUND" ]; then
       echo "ERROR: Stack $STACK_NAME not found"
       exit 1
   fi

   echo "Current status: $STATUS"
   echo

   # Check if rollback is possible
   if [[ "$STATUS" != *"FAILED"* ]] && [[ "$STATUS" != "UPDATE_ROLLBACK_"* ]]; then
       echo "ERROR: Stack is not in a failed state"
       echo "Rollback is only possible after UPDATE_FAILED or CREATE_FAILED"
       exit 1
   fi

   # Confirm rollback
   read -p "Are you sure you want to rollback the stack? (y/n) " -n 1 -r
   echo
   if [[ ! $REPLY =~ ^[Yy]$ ]]; then
       echo "Rollback cancelled"
       exit 0
   fi

   # Perform rollback
   echo "Initiating rollback..."

   if [[ "$STATUS" = "UPDATE_ROLLBACK_FAILED" ]]; then
       # Continue rollback for failed rollback
       aws cloudformation continue-update-rollback \
           --stack-name $STACK_NAME \
           --region $REGION
   elif [[ "$STATUS" = "UPDATE_FAILED" ]]; then
       # CloudFormation automatically rolls back on UPDATE_FAILED
       echo "Stack will automatically rollback to previous state"
   else
       echo "Unexpected status: $STATUS"
       echo "Manual intervention may be required"
       exit 1
   fi

   echo "Waiting for rollback to complete..."
   aws cloudformation wait stack-rollback-complete \
       --stack-name $STACK_NAME \
       --region $REGION || {
       echo "ERROR: Rollback failed or timed out"
       echo "Check CloudFormation console for details"
       exit 1
   }

   echo
   echo "✓ Stack rolled back successfully"
   echo
   echo "Current outputs:"
   aws cloudformation describe-stacks \
       --stack-name $STACK_NAME \
       --region $REGION \
       --query 'Stacks[0].Outputs' \
       --output table
   ```

4. **Make scripts executable:**
   ```bash
   chmod +x infrastructure/scripts/update-stack.sh
   chmod +x infrastructure/scripts/backup-dynamodb.sh
   chmod +x infrastructure/scripts/rollback-stack.sh
   ```

5. **Add rollback data retention policy to master stack:**
   Update `master-stack.yaml` to add retention policies:
   ```yaml
   Resources:
     DatabaseStack:
       Type: AWS::CloudFormation::Stack
       UpdateReplacePolicy: Retain  # Keep tables on stack replacement
       DeletionPolicy: Retain       # Keep tables on stack deletion
       Properties:
         # ... existing properties
   ```

### Verification Checklist

- [ ] Update script creates change sets
- [ ] Change set displays proposed changes
- [ ] Script detects DynamoDB table replacements
- [ ] Backup script creates on-demand backups
- [ ] Rollback script handles failed updates
- [ ] Scripts prompt for confirmation
- [ ] Retention policies added to critical resources
- [ ] Scripts are executable

### Testing Instructions

```bash
# Test change set creation (don't execute)
./infrastructure/scripts/update-stack.sh plot-palette-test development us-east-1
# Select 'n' when prompted to execute

# Test DynamoDB backup
./infrastructure/scripts/backup-dynamodb.sh plot-palette-test us-east-1

# List backups
aws dynamodb list-backups --region us-east-1

# Simulate rollback (only works if stack is in failed state)
# Cannot test without actual failure

# Check retention policies in template
grep -A 2 "RetentionPolicy\|DeletionPolicy" infrastructure/cloudformation/master-stack.yaml
```

### Commit Message Template

```
feat(infrastructure): add safe stack update with change sets and rollback

- Create update script using CloudFormation change sets
- Add DynamoDB backup script for critical data
- Implement rollback script for failed updates
- Detect table replacements that cause data loss
- Add retention policies to prevent data deletion
- Include confirmation prompts for destructive changes
- Automate backup process before risky updates

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 4: Deployment Automation Script

### Goal

Create end-to-end deployment script that orchestrates template upload, validation, stack creation, and monitoring.

### Files to Create

- `infrastructure/scripts/deploy.sh` - Main deployment automation

### Prerequisites

- Tasks 1-3 completed
- AWS CLI configured with appropriate permissions

### Implementation Steps

1. **Script structure** - Combine upload-templates.sh, validate-parameters.sh into single workflow
2. **Deployment modes:**
   - `--create` - Initial stack creation
   - `--update` - Use change sets (from Task 3)
   - `--delete` - Stack deletion with confirmation
3. **Key features to implement:**
   - Check if stack exists, choose create vs update
   - Upload templates to S3
   - Validate parameters
   - Create stack with proper capabilities (CAPABILITY_IAM, CAPABILITY_AUTO_EXPAND)
   - Wait for completion with progress updates
   - Display stack outputs
   - Handle errors with clear messages

**Example flow:**
```bash
# Check stack existence
aws cloudformation describe-stacks --stack-name $STACK_NAME 2>&1 | grep -q "does not exist"

# If exists, use update-stack.sh, otherwise create-stack
aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://... \
    --parameters file://... \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND

# Poll status every 30 seconds, show events
aws cloudformation describe-stack-events --stack-name $STACK_NAME
```

### Verification Checklist

- [ ] Script detects existing vs new stack
- [ ] Creates stack with all parameters
- [ ] Updates stack using change sets
- [ ] Displays progress during deployment
- [ ] Shows final outputs on completion
- [ ] Handles errors with helpful messages

### Testing Instructions

```bash
# Deploy to development
./infrastructure/scripts/deploy.sh --create --environment development --region us-east-1

# Update existing stack
./infrastructure/scripts/deploy.sh --update --environment staging

# Delete stack
./infrastructure/scripts/deploy.sh --delete --stack-name plot-palette-dev
```

### Commit Message Template

```
feat(infrastructure): add automated deployment script for CloudFormation

- Combine template upload, validation, and deployment
- Support create, update, delete operations
- Show deployment progress with stack events
- Display outputs on completion
- Add error handling and rollback support

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~8,000

---

## Task 5: Multi-Region Deployment Support

### Goal

Enable deployment to multiple AWS regions with region-specific considerations (Bedrock availability, service quotas).

### Files to Create

- `infrastructure/scripts/deploy-multi-region.sh` - Multi-region orchestration
- `infrastructure/parameters/regions.json` - Region-specific overrides

### Prerequisites

- Task 4 completed
- Understanding of AWS regional services
- Bedrock model availability by region

### Implementation Steps

1. **Create regions.json with region-specific settings:**
   ```json
   {
     "us-east-1": {
       "BedrockModels": ["anthropic.claude-v2", "meta.llama3-1-70b"],
       "VPCCidr": "10.0.0.0/16"
     },
     "us-west-2": {
       "BedrockModels": ["anthropic.claude-v2"],
       "VPCCidr": "10.1.0.0/16"
     }
   }
   ```

2. **Script requirements:**
   - Loop through target regions
   - Upload templates to region-specific S3 bucket
   - Merge global + region-specific parameters
   - Deploy stack per region
   - Collect outputs from all regions

3. **Key considerations:**
   - Different S3 bucket per region (bucket names are global)
   - Bedrock model availability varies by region
   - Check service quotas (ECS tasks, Cognito users)
   - Route53 for multi-region DNS (optional)

### Verification Checklist

- [ ] Deploys to multiple regions in parallel/sequence
- [ ] Region-specific parameters applied
- [ ] Templates uploaded to correct regional buckets
- [ ] Stack outputs collected from all regions

### Testing Instructions

```bash
# Deploy to multiple regions
./infrastructure/scripts/deploy-multi-region.sh \
    --regions us-east-1,us-west-2 \
    --environment production
```

### Commit Message Template

```
feat(infrastructure): add multi-region deployment support

- Create region-specific parameter overrides
- Deploy stacks across multiple AWS regions
- Handle regional service availability
- Collect outputs from all deployed regions

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~6,000

---

## Task 6: Cost Estimation and Budget Alerts

### Goal

Add CloudFormation template cost estimation and budget tracking for deployed infrastructure.

### Files to Create

- `infrastructure/scripts/estimate-cost.sh` - Cost estimation script
- `infrastructure/cloudformation/budget-stack.yaml` - AWS Budgets template (optional nested stack)

### Prerequisites

- Understanding of AWS pricing
- Cost Explorer API access
- AWS Budgets service

### Implementation Steps

1. **Cost estimation script:**
   - Use AWS Pricing API to estimate infrastructure costs
   - Calculate based on parameter values (environment, instance types, retention)
   - Key resources to estimate:
     - NAT Gateway: ~$32/month
     - ECS Fargate Spot: Varies by task size and duration
     - DynamoDB: On-demand pricing, estimate based on usage
     - Lambda: First 1M requests free, then $0.20/1M
     - S3: Storage + requests
     - Bedrock: Per token pricing (varies by model)
     - Amplify hosting: ~$1-2/month

2. **Budget alerts (optional nested stack):**
   - Create AWS Budget for monthly spend
   - SNS notifications at 80%, 100%, 120% thresholds
   - Link to CostTrackingTable from Phase 4

**Example estimation logic:**
```bash
# Basic monthly estimate for production
NAT_GATEWAY=32  # $32/mo per NAT Gateway
DDB_BASE=25     # Base DynamoDB capacity
S3_STORAGE=10   # 100GB storage
LAMBDA_BASE=5   # Lambda executions
AMPLIFY=2       # Frontend hosting
BEDROCK_VAR=50  # Variable based on usage

TOTAL=$((NAT_GATEWAY + DDB_BASE + S3_STORAGE + LAMBDA_BASE + AMPLIFY + BEDROCK_VAR))
echo "Estimated monthly cost: $$TOTAL"
```

3. **Budget stack template** - Create budget resource with notifications

### Verification Checklist

- [ ] Script estimates infrastructure costs
- [ ] Budget stack creates AWS Budget
- [ ] SNS notifications configured
- [ ] Alerts trigger at thresholds

### Testing Instructions

```bash
# Estimate cost for production deployment
./infrastructure/scripts/estimate-cost.sh --environment production

# Deploy budget stack
aws cloudformation create-stack \
    --stack-name plot-palette-budget \
    --template-body file://infrastructure/cloudformation/budget-stack.yaml
```

### Commit Message Template

```
feat(infrastructure): add cost estimation and budget alerts

- Create script to estimate deployment costs
- Add AWS Budgets template for spend tracking
- Configure SNS alerts for budget thresholds
- Document cost breakdown by service

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~7,000

---

## Task 7: Deployment Documentation

### Goal

Create comprehensive deployment guide with troubleshooting and best practices.

### Files to Create

- `docs/deployment/README.md` - Deployment guide
- `docs/deployment/troubleshooting.md` - Common issues and fixes
- `docs/deployment/disaster-recovery.md` - Backup and recovery procedures

### Prerequisites

- All previous tasks completed
- Successful test deployments

### Implementation Steps

1. **README.md structure:**
   - Prerequisites (AWS account, CLI, permissions)
   - Quick start (5-minute deployment)
   - Detailed step-by-step guide
   - Environment-specific instructions
   - Post-deployment validation
   - Accessing the application

2. **troubleshooting.md - Document common issues:**
   - Stack creation failures (IAM permissions, quota limits)
   - Nested stack errors (template upload issues)
   - DynamoDB table already exists
   - Bedrock access denied
   - VPC quota exceeded
   - ECS task failures
   - Each issue with solution steps

3. **disaster-recovery.md:**
   - Backup strategy (DynamoDB PITR, S3 versioning)
   - Recovery procedures
   - Multi-region failover
   - Data retention policies
   - RTO/RPO targets

**Key sections to include:**

```markdown
## Quick Start

1. Configure AWS CLI: `aws configure`
2. Validate Bedrock access
3. Run deployment: `./infrastructure/scripts/deploy.sh --create --environment production`
4. Access application at CloudFormation output URL

## Common Issues

### Stack creation fails with "Template too large"
- **Cause:** Master template exceeds 51,200 bytes
- **Solution:** Templates must be uploaded to S3 first

### DynamoDB table already exists
- **Cause:** Previous deployment not cleaned up
- **Solution:** Delete existing tables or use different environment name
```

### Verification Checklist

- [ ] Deployment guide covers all prerequisites
- [ ] Step-by-step instructions tested
- [ ] Troubleshooting guide has solutions
- [ ] Disaster recovery procedures documented
- [ ] Examples and screenshots included

### Testing Instructions

- Follow deployment guide on fresh AWS account
- Verify all commands work as documented
- Test troubleshooting steps for common issues

### Commit Message Template

```
docs(deployment): add comprehensive deployment and troubleshooting guides

- Create step-by-step deployment instructions
- Document common issues and solutions
- Add disaster recovery procedures
- Include environment-specific guidance
- Provide post-deployment validation steps

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~10,000

---

## Phase 7 Verification

**Success Criteria:**

- [ ] Master stack deploys all nested stacks
- [ ] Parameters validated before deployment
- [ ] Update process uses change sets
- [ ] DynamoDB backups created automatically
- [ ] Deployment script automates entire process
- [ ] Multi-region deployment supported
- [ ] Cost estimation available
- [ ] Comprehensive documentation complete

**Estimated Total Tokens:** ~95,000

---

**Navigation:**
- [← Previous: Phase 6](./Phase-6.md)
- [Next: Phase 8 - Integration Testing →](./Phase-8.md)
