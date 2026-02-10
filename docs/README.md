<div align="center" style="display: block;margin-left: auto;margin-right: auto;width: 70%;">
<h1>Plot Palette</h1>

<h4 align="center">
<a href="https://www.apache.org/licenses/LICENSE-2.0.html"><img src="https://img.shields.io/badge/license-Apache2.0-blue" alt="Plot Palette is under the Apache 2.0 license" /></a><a href="https://aws.amazon.com/bedrock/"><img src="https://img.shields.io/badge/AWS%20Bedrock-orange" alt="AWS Bedrock" /></a><a href="https://aws.amazon.com/sam/"><img src="https://img.shields.io/badge/AWS%20SAM-yellow" alt="AWS SAM" /></a><a href="https://react.dev/"><img src="https://img.shields.io/badge/React-19-61DAFB" alt="React 19" /></a><a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.13-blue" alt="Python 3.13" /></a><a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-24-green" alt="Node.js 24" /></a>
</h4>
<p align="center">
  <p align="center"><b>Production-Ready Serverless Synthetic Data Generator<br> <a href="https://huggingface.co/datasets/Hatman/plot-palette-100k"> Plot Palette Dataset » </a> </b> </p>
</p>
<h1 align="center">
  <img width="400" src="../banner.png" alt="plot-palette icon">
</h1>
<p>Generate synthetic training data at scale using AWS Bedrock foundation models. Leverage ECS Fargate Spot instances for up to 70% cost savings with automatic checkpoint recovery. Configure jobs, upload seed data, and monitor progress through a modern React web interface.</p>
</div>

## Features

- **Web-Based UI**: Modern React interface for job management, template editing, and real-time monitoring
- **Custom Prompt Templates**: Multi-step generation flows with Jinja2 templating, conditional logic, and variable substitution
- **Multiple Export Formats**: JSONL, Parquet, and CSV with configurable partitioning strategies
- **Budget Controls**: Hard budget limits to prevent runaway costs with real-time cost tracking
- **Smart Model Routing**: Use cost-efficient models for simple tasks, premium models for complex reasoning
- **Checkpoint Recovery**: Automatic recovery from Fargate Spot interruptions with minimal data loss
- **Multi-Region Support**: Deploy in any AWS region with Bedrock availability

## Technologies Used

- **AWS Bedrock**: LLM inference (Claude, Llama, Mistral models)
- **ECS Fargate Spot**: Cost-optimized compute for generation workers (up to 70% savings)
- **AWS Lambda**: Serverless API handlers
- **DynamoDB**: State management, job queue, and cost tracking
- **S3**: Object storage for seed data, checkpoints, and outputs
- **API Gateway v2**: HTTP API with JWT authorization
- **Cognito**: User authentication and management
- **React + Vite**: Modern frontend with TypeScript

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/HatmanStack/plot-palette.git
   cd plot-palette
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Deploy the backend** (creates Lambda, DynamoDB, S3, API Gateway, ECS):
   ```bash
   npm run deploy
   ```

   You'll be prompted for:
   - AWS region
   - Stack name
   - Environment (development/production)

   See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed configuration options.

4. **Start the development server**:
   ```bash
   npm start
   ```

## Usage

### Creating a Generation Job

1. Navigate to **Jobs** → **Create New Job**
2. Select a prompt template or create a new one
3. Upload seed data (JSON array of objects)
4. Configure parameters:
   - Number of records to generate
   - Budget limit (USD)
   - Output format (JSONL, Parquet, CSV)
   - Model selection
5. Click **Start Job**

### Managing Templates

Templates use Jinja2 syntax with custom filters:

```jinja
Generate a {{ category }} story about {{ topic }}.

{% if style %}
Write in a {{ style }} style.
{% endif %}

Use these seed words: {{ keywords | join(', ') }}
```

Available filters: `json`, `join`, `upper`, `lower`, `capitalize`, `random_choice`, `shuffle`

### Monitoring Jobs

The dashboard shows:
- Job status (Queued, Running, Completed, Failed, Budget Exceeded)
- Records generated / total
- Current cost / budget limit
- Estimated completion time

### Downloading Results

Completed jobs provide download links for:
- Generated data (JSONL/Parquet/CSV)
- Generation logs
- Cost breakdown

## Architecture

**Frontend**: React + Vite + TypeScript
- React Query for data fetching
- React Router for navigation
- Tailwind CSS for styling

**Backend**: AWS Serverless
- 14 Lambda functions for API endpoints
- ECS Fargate Spot workers for generation
- DynamoDB for state management
- S3 for storage with lifecycle policies

**Storage Layout**:
```
s3://plot-palette-{account}-{region}/
├── seed-data/{user-id}/       # User seed data uploads
├── checkpoints/{job-id}/      # Generation checkpoints
├── outputs/{job-id}/          # Generated data batches
└── exports/{job-id}/          # Final exported files
```

## Testing

```bash
npm run check         # Run all lint and tests
npm test              # Frontend tests only
npm run test:backend  # Backend tests only
npm run lint          # Frontend ESLint + TypeScript
npm run lint:backend  # Backend ruff
```

**Test Coverage**:
Run `npm run check` to see current test counts.

## API Reference

See [`openapi.yaml`](openapi.yaml) for the full OpenAPI 3.0 specification covering all 16 API endpoints.

## AWS Bedrock Models

**Tier 1 (Cost-Efficient)**:
- Amazon Titan Text
- Qwen3-32B (Dense)

**Tier 2 (Balanced)**:
- Qwen3-235B-A22B-Instruct
- Meta Llama 3.3 70B

**Tier 3 (Premium)**:
- Anthropic Claude 4.5 Haiku

See [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) for current rates.

## License

Apache 2.0 - See [LICENSE](../LICENSE) for details.

**Model Output Licenses**: Generated data may have restrictions based on the Bedrock models used. Review each provider's terms:
- [Anthropic Terms](https://www.anthropic.com/legal/commercial-terms)
- [Meta Llama License](https://llama.meta.com/llama3/license/)
- [Mistral AI Terms](https://mistral.ai/terms/)
