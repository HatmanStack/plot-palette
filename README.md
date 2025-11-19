<div align="center" style="display: block;margin-left: auto;margin-right: auto;width: 50%;">
<h1 >
  <img width="400" height="100" src="banner.png" alt="plot-palette icon">
</h1>
<div style="display: flex; justify-content: center; align-items: center;">
  <h4 style="margin: 0; display: flex;">
    <a href="https://www.apache.org/licenses/LICENSE-2.0.html">
      <img src="https://img.shields.io/badge/license-Apache2.0-blue" alt="float is under the Apache 2.0 license" />
    </a>
    <a href="https://aws.amazon.com/bedrock/">
      <img src="https://img.shields.io/badge/AWS%20Bedrock-orange" alt="AWS Bedrock" />
    </a>
    <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.13-blue">
    </a>
  </h4>
</div>

  <p><b>Production-Ready Serverless Synthetic Data Generator <br> <a href="https://huggingface.co/datasets/Hatman/plot-palette-100k"> Plot Palette Dataset HuggingFace » </a> </b> </p>
</div>

**Plot Palette** is a production-ready, serverless AWS application that generates synthetic training data using AWS Bedrock foundation models. The system leverages ECS Fargate Spot instances to opportunistically consume spare compute capacity at up to **70% cost savings**, with robust checkpoint-based recovery for spot interruptions.

Users interact with a modern React web application to configure generation jobs, upload seed data, customize prompt templates, and monitor real-time progress with cost tracking. The architecture is fully serverless (except for generation workers), with automatic scaling, multi-region support, and one-click CloudFormation deployment. 

## Architecture

```
┌─────────────┐
│   Users     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS Amplify (React UI)                   │
│  • Job Creation  • Template Management  • Real-time Tracking│
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              API Gateway (HTTP API) + Cognito               │
│         • JWT Authentication  • REST Endpoints              │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ Lambda   │   │ Lambda   │   │ Lambda   │
      │ Create   │   │ Monitor  │   │ Export   │
      │ Job      │   │ Jobs     │   │ Data     │
      └────┬─────┘   └────┬─────┘   └────┬─────┘
           │              │              │
           ▼              ▼              ▼
      ┌────────────────────────────────────┐
      │         DynamoDB Tables            │
      │  Jobs | Queue | Templates | Costs  │
      └────────────────┬───────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  ECS Fargate   │
              │  Spot Workers  │
              │  • Checkpoint  │
              │  • Recovery    │
              └───┬────────┬───┘
                  │        │
         ┌────────┘        └────────┐
         ▼                          ▼
    ┌─────────┐              ┌──────────┐
    │   S3    │              │  Bedrock │
    │ Storage │              │   LLMs   │
    └─────────┘              └──────────┘
```

## Key Features

- **Web-Based UI**: Modern React interface for job management and monitoring
- **Real-Time Progress Tracking**: Live updates on generation progress and cost accumulation
- **Custom Prompt Templates**: Multi-step generation flows with conditional logic and variable substitution
- **Multiple Export Formats**: JSONL, Parquet, and CSV with configurable partitioning
- **Automatic Glacier Archival**: Cost optimization with automatic archival after 3 days
- **Budget Limits**: Hard budget caps to prevent runaway costs
- **Smart Model Routing**: Use cost-efficient models for simple tasks, premium models for complex reasoning
- **Checkpoint Recovery**: Automatic recovery from Fargate Spot interruptions with minimal data loss
- **Multi-Region Support**: Deploy in any AWS region with Bedrock availability

## AWS Services Used

- **AWS Bedrock**: LLM inference (Claude, Llama, Mistral models)
- **ECS Fargate Spot**: Cost-optimized compute for generation workers
- **S3**: Object storage for seed data, checkpoints, and outputs
- **DynamoDB**: State management, job queue, and cost tracking
- **API Gateway**: HTTP API with JWT authorization
- **Cognito**: User authentication and management
- **Amplify**: Frontend hosting and deployment
- **CloudWatch Logs**: Centralized logging and monitoring
- **CloudFormation**: Infrastructure as Code deployment

## Quick Start

### Prerequisites

**AWS Account Setup:**
- AWS Account with administrator or PowerUser permissions
- AWS CLI v2+ installed and configured (`aws configure`)
- AWS Bedrock access enabled in target region (request model access via AWS Console)

**Local Development Tools:**
- Python 3.13+ installed
- Node.js 20+ and npm for frontend development
- Git for version control
- `jq` for JSON parsing (used by deployment script)

### Deployment

1. **Clone the Repository**
   ```bash
   git clone https://github.com/HatmanStack/plot-palette.git
   cd plot-palette
   ```

2. **Deploy Infrastructure**
   ```bash
   # Deploy all infrastructure stacks to AWS
   ./infrastructure/scripts/deploy.sh --region us-east-1 --environment production
   ```

   The deployment script will:
   - Create VPC and networking infrastructure
   - Set up S3 bucket with lifecycle policies
   - Create DynamoDB tables
   - Configure IAM roles and policies
   - Generate `outputs.json` with all resource details

3. **Access the Application**

   After deployment completes, the Amplify frontend URL will be available in Phase 6. For Phase 1, infrastructure is deployed but application code will be added in subsequent phases.

### Deployment Options

```bash
# Deploy to a specific region
./infrastructure/scripts/deploy.sh --region us-west-2 --environment production

# Deploy development environment
./infrastructure/scripts/deploy.sh --region us-east-1 --environment development

# Delete all infrastructure (cleanup)
./infrastructure/scripts/deploy.sh --delete --environment test
```

### Estimated Costs

**Idle Infrastructure (Phase 1 only):**
- VPC, Subnets, Internet Gateway: **$0/month** (free)
- S3 bucket (empty): **$0/month**
- DynamoDB (on-demand, no traffic): **$0/month**
- IAM roles: **$0/month**

**Expected Monthly Costs (with active usage):**
- ECS Fargate Spot: $5-20 (70% cheaper than on-demand)
- AWS Bedrock: $10-100 (depends on token usage)
- S3 Storage: $1-5
- DynamoDB: $1-3
- API Gateway: $0-1 (first 1M requests free)
- Total: **~$20-140/month** depending on generation volume

### Recommended Regions

- **us-east-1** (Virginia): Broadest Bedrock model availability
- **us-west-2** (Oregon): Good Bedrock support, lower costs
- **eu-west-1** (Ireland): European data residency  

## AWS Bedrock Models Available

The system uses AWS Bedrock for LLM inference with smart model routing:

**Tier 1 (Cost-Efficient):**
- `meta.llama3-1-8b-instruct-v1:0` - Llama 3.1 8B ($0.30 input / $0.60 output per 1M tokens)
- `mistral.mistral-7b-instruct-v0:2` - Mistral 7B ($0.15 input / $0.20 output per 1M tokens)

**Tier 2 (Balanced):**
- `meta.llama3-1-70b-instruct-v1:0` - Llama 3.1 70B ($0.99 input / $0.99 output per 1M tokens)

**Tier 3 (Premium):**
- `anthropic.claude-3-5-sonnet-20241022-v2:0` - Claude 3.5 Sonnet ($3.00 input / $15.00 output per 1M tokens)

Smart routing allows you to use cheap models for simple transformations and premium models for complex reasoning, optimizing cost vs. quality.

## Example Dataset

The original [Plot Palette 100k dataset](https://huggingface.co/datasets/Hatman/plot-palette-100k) was generated using an earlier version of this system. The new AWS-based architecture provides:
- Better cost efficiency (70% savings with Fargate Spot)
- Web-based management interface
- Custom prompt templates
- Automatic checkpointing and recovery
- Multiple export formats

```python
# Load the example dataset
from datasets import load_dataset
ds = load_dataset("Hatman/plot-palette-100k")
```

## Migration from v1 (systemd-based)

**Breaking Changes:**

The system has been completely rewritten from a systemd-based Python script to a serverless AWS application. The v1 systemd service files and local Python scripts are **no longer used**.

**Migration Steps:**

1. **Export your v1 seed data** from local storage
2. **Deploy the new AWS infrastructure** using the deployment script
3. **Upload seed data to S3** via the web UI (available in Phase 6) or AWS CLI:
   ```bash
   aws s3 cp main_dictionary.json s3://plot-palette-{account-id}-{region}-production/seed-data/
   ```
4. **Create prompt templates** in the web UI matching your v1 generation logic
5. **Run generation jobs** through the web interface

**What's Different:**

| v1 (systemd) | v2 (AWS Serverless) |
|--------------|---------------------|
| Local Python scripts | ECS Fargate workers |
| systemctl service | Web UI + API Gateway |
| Local file storage | S3 with Glacier archival |
| No cost tracking | Real-time cost monitoring |
| Manual recovery | Automatic checkpoint recovery |
| Single model | Multi-model with smart routing |

**Support:**

If you need help migrating, please open a GitHub issue with details about your v1 setup.

## Project Structure

```
plot-palette/
├── infrastructure/
│   ├── cloudformation/          # CloudFormation templates
│   │   ├── network-stack.yaml
│   │   ├── storage-stack.yaml
│   │   ├── database-stack.yaml
│   │   └── iam-stack.yaml
│   └── scripts/
│       └── deploy.sh            # Deployment automation
├── backend/
│   ├── shared/                  # Shared Python library
│   ├── lambdas/                 # API Lambda functions (Phase 3)
│   └── ecs_tasks/               # Fargate generation workers (Phase 4)
├── frontend/                    # React web application (Phase 6)
├── tests/                       # Unit, integration, e2e tests
└── docs/plans/                  # Implementation plan documentation
```

## Development

See `docs/plans/README.md` for detailed implementation phases and development workflow.

## License

This project is licensed under the Apache 2.0 License. See LICENSE file for details.

**Model Output Licenses:**

When using AWS Bedrock models, refer to each model provider's terms:
- **Anthropic Claude**: [Anthropic Terms of Service](https://www.anthropic.com/legal/commercial-terms)
- **Meta Llama**: [Llama 3.1 Community License](https://llama.meta.com/llama3/license/)
- **Mistral AI**: [Mistral AI Terms](https://mistral.ai/terms/)

Generated datasets may have restrictions based on the models used. Always review model provider terms before using outputs for commercial purposes or training other models. 

<p align="center">
    This application is using HuggingFace Tokenizers provided by <a href="https://huggingface.co">HuggingFace</a> </br>
    <img src="https://github.com/HatmanStack/pixel-prompt-backend/blob/main/logo.png" alt="HuggingFace Logo">
</p>