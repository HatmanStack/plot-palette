# AWS Setup Guide

## Prerequisites

- **AWS account** with permissions to create IAM roles, Lambda functions, DynamoDB tables, S3 buckets, ECS clusters, Step Functions, and Cognito user pools.
- **AWS CLI** v2 configured with credentials (`aws configure`).
- **AWS SAM CLI** v1.100+ for serverless deployment.
- **Docker** for building Lambda layers and ECS container images.

## Enable Bedrock Models

Bedrock models require explicit enablement per region. In the AWS Console:

1. Navigate to **Amazon Bedrock** > **Model access** in your target region (default: `us-east-1`).
2. Request access for the models used by Plot Palette:
   - **Meta Llama 3.1 8B Instruct** (tier-1, cheapest)
   - **Meta Llama 3.1 70B Instruct** (tier-2, balanced)
   - **Anthropic Claude 3.5 Sonnet** (tier-3, premium)
3. Wait for access to be granted (usually instant for Llama, may take minutes for Claude).

Without model access, generation jobs will fail with `AccessDeniedException`.

## Deploy

```bash
npm run deploy
```

The deploy script prompts for:

| Prompt | Description | Default |
|--------|-------------|---------|
| Stack Name | CloudFormation stack name | `plot-palette` |
| AWS Region | Deployment region | `us-east-1` |
| Environment | `development` or `production` | `development` |

After deployment completes, SAM outputs the values needed for `.env`:

```bash
# Copy .env.example and fill in values from SAM output
cp .env.example .env
```

| `.env` Variable | SAM Output |
|----------------|------------|
| `VITE_API_ENDPOINT` | `ApiEndpoint` |
| `VITE_USER_POOL_ID` | `UserPoolId` |
| `VITE_USER_POOL_CLIENT_ID` | `UserPoolClientId` |
| `VITE_REGION` | Your chosen region |

## Cognito User Setup

After deployment, create a user in the Cognito User Pool:

```bash
# Create user (replace with your values from SAM output)
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username your@email.com \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username your@email.com \
  --password YourPermanentPass123! \
  --permanent
```

## Cost Expectations

Plot Palette costs scale with usage. With no active jobs, costs are near zero (DynamoDB on-demand, no running Fargate tasks).

| Resource | Pricing Model | Typical Cost |
|----------|--------------|--------------|
| Bedrock (Llama 8B) | ~$0.30/M input tokens, ~$0.60/M output tokens | ~$0.01-0.05 per 100 records |
| Bedrock (Claude 3.5 Sonnet) | ~$3.00/M input, ~$15.00/M output | ~$0.10-0.50 per 100 records |
| Fargate Spot | ~$0.012/vCPU/hr, ~$0.0013/GB/hr | ~$0.02-0.10 per job |
| DynamoDB | Pay-per-request | ~$0.001 per job |
| S3 | $0.023/GB/month + request fees | Negligible |

Budget limits in job config prevent runaway costs. The worker checks accumulated cost against the budget after each batch.
