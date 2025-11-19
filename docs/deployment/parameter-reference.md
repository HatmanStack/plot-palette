# CloudFormation Parameter Reference

Complete reference for all CloudFormation parameters used in Plot Palette deployment.

## Overview

Parameters are specified in environment-specific JSON files:
- `infrastructure/parameters/production.json`
- `infrastructure/parameters/staging.json`
- `infrastructure/parameters/development.json`

## Parameter Format

CloudFormation parameter files use array format:

```json
[
  {
    "ParameterKey": "ParameterName",
    "ParameterValue": "value"
  }
]
```

---

## Required Parameters

### EnvironmentName

**Type:** String
**Allowed Values:** `development`, `staging`, `production`
**Description:** Environment name used for resource tagging and naming conventions.

**Example:**
```json
{
  "ParameterKey": "EnvironmentName",
  "ParameterValue": "production"
}
```

**Impact:**
- Resource names: `plot-palette-{resource}-{environment}`
- CloudWatch log groups: `/aws/lambda/plot-palette-{environment}`
- Tags applied to all resources

**Validation:**
- Must be one of: `development`, `staging`, `production`
- Cannot be changed after stack creation (requires replacement)

---

### AdminEmail

**Type:** String
**Pattern:** `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
**Description:** Email address for the initial administrator user and system notifications.

**Example:**
```json
{
  "ParameterKey": "AdminEmail",
  "ParameterValue": "admin@example.com"
}
```

**Impact:**
- Used for Cognito User Pool admin user creation
- Future: SNS notifications for budget alerts
- CloudFormation stack notifications

**Validation:**
- Must be valid email format
- Validated by `validate-parameters.sh` script

**Best Practices:**
- Use distribution list for production
- Use personal email for development
- Ensure mailbox is monitored

---

## Optional Parameters

### InitialBudgetLimit

**Type:** Number
**Range:** 1 - 10000
**Default:** 100
**Unit:** USD
**Description:** Default budget limit for generation jobs.

**Example:**
```json
{
  "ParameterKey": "InitialBudgetLimit",
  "ParameterValue": "100"
}
```

**Impact:**
- Sets default budget for new jobs created via API
- Users can override per-job via API parameter
- Hard limit enforced by generation workers
- No AWS Budget resource created (just default value)

**Recommended Values:**

| Environment | Value | Rationale |
|-------------|-------|-----------|
| Development | 10    | Low-cost testing |
| Staging     | 50    | Pre-production validation |
| Production  | 100   | Production workloads |

**Notes:**
- Actual cost depends on token usage and compute hours
- Budget enforcement prevents runaway costs
- See cost estimation: `./infrastructure/scripts/estimate-cost.sh`

---

### LogRetentionDays

**Type:** Number
**Allowed Values:** 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365
**Default:** 7
**Description:** CloudWatch Logs retention period in days.

**Example:**
```json
{
  "ParameterKey": "LogRetentionDays",
  "ParameterValue": "30"
}
```

**Impact:**
- Applies to all Lambda function logs
- Applies to ECS task logs
- Older logs automatically deleted
- Affects CloudWatch storage costs

**Cost Impact:**

| Retention | Monthly Cost (estimate) |
|-----------|------------------------|
| 1 day     | $0.50 |
| 7 days    | $2.00 |
| 30 days   | $5.00 |
| 90 days   | $10.00 |

**Recommended Values:**

| Environment | Value | Rationale |
|-------------|-------|-----------|
| Development | 1     | Minimal cost |
| Staging     | 7     | Short-term debugging |
| Production  | 30    | Compliance and debugging |

**Compliance Note:**
- Some regulations require 90+ days log retention
- Adjust based on your compliance requirements

---

### TemplatesBucketName

**Type:** String
**Default:** "" (empty = create new bucket)
**Description:** Existing S3 bucket name containing CloudFormation templates.

**Example (use existing bucket):**
```json
{
  "ParameterKey": "TemplatesBucketName",
  "ParameterValue": "my-cfn-templates-bucket"
}
```

**Example (create new bucket):**
```json
{
  "ParameterKey": "TemplatesBucketName",
  "ParameterValue": ""
}
```

**Impact:**
- If empty: Creates new bucket `plot-palette-cfn-{account-id}-{region}`
- If specified: Uses existing bucket (must already contain templates)

**When to Specify:**
- You have centralized CFN template storage
- Multiple stacks share same template bucket
- Cross-region deployments (bucket must exist in each region)

**When to Leave Empty:**
- First deployment
- Isolated stack deployments
- Simplest option (recommended)

**Bucket Requirements (if specified):**
- Must exist in same region as stack
- Must contain all nested stack templates
- Must allow CloudFormation access
- Versioning recommended

---

## Environment-Specific Configurations

### Development Environment

**Optimized for:** Low cost, fast iteration

```json
[
  {
    "ParameterKey": "EnvironmentName",
    "ParameterValue": "development"
  },
  {
    "ParameterKey": "AdminEmail",
    "ParameterValue": "dev@example.com"
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

**Estimated Monthly Cost:** $5-15

---

### Staging Environment

**Optimized for:** Pre-production testing

```json
[
  {
    "ParameterKey": "EnvironmentName",
    "ParameterValue": "staging"
  },
  {
    "ParameterKey": "AdminEmail",
    "ParameterValue": "staging-admin@example.com"
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

**Estimated Monthly Cost:** $15-50

---

### Production Environment

**Optimized for:** Reliability, compliance

```json
[
  {
    "ParameterKey": "EnvironmentName",
    "ParameterValue": "production"
  },
  {
    "ParameterKey": "AdminEmail",
    "ParameterValue": "admin@example.com"
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

**Estimated Monthly Cost:** $50-200

---

## Validation

### Automated Validation

Use the validation script before deployment:

```bash
./infrastructure/scripts/validate-parameters.sh production
```

**Checks performed:**
- JSON syntax validation
- Email format validation
- Budget limit range (1-10000)
- Log retention allowed values
- Environment name allowed values
- AWS credentials configured
- Bedrock access available

### Manual Validation

```bash
# Validate JSON syntax
jq empty infrastructure/parameters/production.json

# Extract specific parameter
jq -r '.[] | select(.ParameterKey=="AdminEmail") | .ParameterValue' \
    infrastructure/parameters/production.json
```

---

## Parameter Override

### CLI Override

Override parameters during deployment:

```bash
aws cloudformation create-stack \
    --stack-name plot-palette \
    --template-body file://infrastructure/cloudformation/master-stack.yaml \
    --parameters \
        ParameterKey=EnvironmentName,ParameterValue=production \
        ParameterKey=AdminEmail,ParameterValue=override@example.com \
        ParameterKey=InitialBudgetLimit,ParameterValue=200
```

### Mixed File + Override

Use parameter file with selective overrides:

```bash
aws cloudformation create-stack \
    --stack-name plot-palette \
    --parameters \
        file://infrastructure/parameters/production.json \
        ParameterKey=InitialBudgetLimit,ParameterValue=200,UsePreviousValue=false
```

**Note:** Later parameters override earlier ones.

---

## Updating Parameters

### Safe Update Process

1. Edit parameter file:
```bash
vim infrastructure/parameters/production.json
```

2. Validate changes:
```bash
./infrastructure/scripts/validate-parameters.sh production
```

3. Review impact with change set:
```bash
./infrastructure/scripts/update-stack.sh plot-palette production us-east-1
```

4. Changes requiring replacement are flagged (e.g., EnvironmentName)

### Parameters That Cause Replacement

**EnvironmentName:**
- Changing this replaces most resources
- **Requires data migration**
- Not recommended for production

**Recommendation:** Deploy new stack with new environment name instead of updating.

---

## Best Practices

1. **Version Control:** Commit parameter files to Git
2. **Secrets:** Never commit passwords or API keys in parameter files
3. **Email Validation:** Use script validation before deployment
4. **Cost Review:** Run cost estimation after parameter changes
5. **Separate Environments:** Maintain distinct parameter files per environment
6. **Document Changes:** Use Git commit messages to track parameter changes

---

## See Also

- [Deployment Guide](./README.md)
- [Cost Estimation](../../infrastructure/scripts/estimate-cost.sh)
- [Troubleshooting](./troubleshooting.md)
