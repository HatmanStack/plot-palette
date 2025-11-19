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

---

## Task 1: Master Stack Template

### Goal

Create master CloudFormation template that orchestrates all nested stacks in correct order.

### Files to Create

- `infrastructure/cloudformation/master-stack.yaml` - Master template
- `infrastructure/scripts/upload-templates.sh` - Upload nested templates to S3

### Implementation Steps

1. **Create master-stack.yaml structure:**
   ```yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'Plot Palette - Synthetic Data Generator (Master Stack)'

   Parameters:
     EnvironmentName:
       Type: String
       Default: production
       AllowedValues: [development, staging, production]

     AdminEmail:
       Type: String
       Description: Email for admin user and notifications

     InitialBudgetLimit:
       Type: Number
       Default: 100
       Description: Default budget limit for jobs (USD)

   Resources:
     NetworkStack:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/network-stack.yaml
         Parameters:
           EnvironmentName: !Ref EnvironmentName

     StorageStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: NetworkStack
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/storage-stack.yaml
         Parameters:
           EnvironmentName: !Ref EnvironmentName

     DatabaseStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: StorageStack
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/database-stack.yaml
         Parameters:
           EnvironmentName: !Ref EnvironmentName

     IAMStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [StorageStack, DatabaseStack]
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/iam-stack.yaml
         Parameters:
           S3BucketName: !GetAtt StorageStack.Outputs.BucketName
           JobsTableArn: !GetAtt DatabaseStack.Outputs.JobsTableArn
           QueueTableArn: !GetAtt DatabaseStack.Outputs.QueueTableArn
           TemplatesTableArn: !GetAtt DatabaseStack.Outputs.TemplatesTableArn
           CostTrackingTableArn: !GetAtt DatabaseStack.Outputs.CostTrackingTableArn
         Capabilities: [CAPABILITY_IAM]

     AuthStack:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/auth-stack.yaml
         Parameters:
           EnvironmentName: !Ref EnvironmentName
           AdminEmail: !Ref AdminEmail

     APIStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [AuthStack, IAMStack]
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/api-stack.yaml
         Parameters:
           UserPoolId: !GetAtt AuthStack.Outputs.UserPoolId
           UserPoolClientId: !GetAtt AuthStack.Outputs.UserPoolClientId
           LambdaExecutionRoleArn: !GetAtt IAMStack.Outputs.LambdaExecutionRoleArn

     ComputeStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: IAMStack
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/compute-stack.yaml
         Parameters:
           EnvironmentName: !Ref EnvironmentName
           ECSTaskRoleArn: !GetAtt IAMStack.Outputs.ECSTaskRoleArn

     FrontendStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: [APIStack, AuthStack]
       Properties:
         TemplateURL: !Sub https://${TemplatesBucket}.s3.amazonaws.com/frontend-stack.yaml
         Parameters:
           ApiEndpoint: !GetAtt APIStack.Outputs.ApiEndpoint
           UserPoolId: !GetAtt AuthStack.Outputs.UserPoolId
           UserPoolClientId: !GetAtt AuthStack.Outputs.UserPoolClientId
           AmplifyServiceRoleArn: !GetAtt IAMStack.Outputs.AmplifyServiceRoleArn

   Outputs:
     ApiEndpoint:
       Description: API Gateway endpoint
       Value: !GetAtt APIStack.Outputs.ApiEndpoint

     UserPoolId:
       Description: Cognito User Pool ID
       Value: !GetAtt AuthStack.Outputs.UserPoolId

     FrontendUrl:
       Description: Amplify frontend URL
       Value: !GetAtt FrontendStack.Outputs.AmplifyAppUrl

     BucketName:
       Description: S3 bucket name
       Value: !GetAtt StorageStack.Outputs.BucketName
   ```

2. **Create upload script** (`infrastructure/scripts/upload-templates.sh`):
   ```bash
   #!/bin/bash
   set -e

   REGION=${1:-us-east-1}
   BUCKET_NAME="plot-palette-cfn-templates-${AWS_ACCOUNT_ID}-${REGION}"

   # Create templates bucket if doesn't exist
   aws s3 mb s3://$BUCKET_NAME --region $REGION || true

   # Upload all nested templates
   aws s3 sync infrastructure/cloudformation/ s3://$BUCKET_NAME/ \
     --exclude "master-stack.yaml" \
     --region $REGION

   echo "Templates uploaded to s3://$BUCKET_NAME/"
   ```

**Estimated Tokens:** ~20,000

---

## Task 2: Parameter Management

### Goal

Centralize parameter management and validation.

**Key Points:**
- Environment-specific parameter files
- Parameter validation
- Sensitive parameter handling (Secrets Manager)
- Default values

**Estimated Tokens:** ~12,000

---

## Task 3: Stack Update Strategy

### Goal

Implement safe stack update process with backup and rollback.

**Features:**
- Change set preview
- Backup DynamoDB tables before update
- Rolling update for ECS tasks
- Rollback on failure

**Estimated Tokens:** ~15,000

---

## Task 4: Complete Deployment Script

### Goal

Enhance deployment script to handle full stack lifecycle.

**Capabilities:**
- Deploy master stack
- Update existing stack
- Delete stack with confirmation
- Export outputs to JSON
- Health checks after deployment

**Estimated Tokens:** ~18,000

---

## Task 5: Multi-Region Support

### Goal

Enable deployment to multiple AWS regions.

**Features:**
- Region-specific parameters
- Cross-region references handled
- Regional service availability checks

**Estimated Tokens:** ~12,000

---

## Task 6: Cost Estimation

### Goal

Provide cost estimates before deployment.

**Implementation:**
- Calculate monthly costs based on parameters
- Show cost breakdown by service
- Compare costs across regions

**Estimated Tokens:** ~10,000

---

## Task 7: Deployment Documentation

### Goal

Document deployment process and troubleshooting.

**Documentation:**
- Prerequisites
- Step-by-step deployment guide
- Parameter reference
- Troubleshooting common issues
- Rollback procedures

**Estimated Tokens:** ~8,000

---

## Phase 7 Verification

**Success Criteria:**
- [ ] Master stack deploys all nested stacks
- [ ] Parameters passed correctly
- [ ] Stack updates work safely
- [ ] Rollback works on failure
- [ ] Multi-region deployment works
- [ ] Cost estimation accurate
- [ ] Documentation complete

---

**Navigation:**
- [← Previous: Phase 6](./Phase-6.md)
- [Next: Phase 8 - Integration Testing →](./Phase-8.md)
