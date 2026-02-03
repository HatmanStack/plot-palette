<div align="center" style="display: block;margin-left: auto;margin-right: auto;width: 70%;">
<h1>Plot Palette</h1>

<h4 align="center">
<a href="https://www.apache.org/licenses/LICENSE-2.0.html"><img src="https://img.shields.io/badge/license-Apache2.0-blue" alt="Plot Palette is under the Apache 2.0 license" /></a><a href="https://aws.amazon.com/bedrock/"><img src="https://img.shields.io/badge/AWS%20Bedrock-orange" alt="AWS Bedrock" /></a><a href="https://aws.amazon.com/sam/"><img src="https://img.shields.io/badge/AWS%20SAM-yellow" alt="AWS SAM" /></a><a href="https://react.dev/"><img src="https://img.shields.io/badge/React-19-61DAFB" alt="React 19" /></a><a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.13-blue" alt="Python 3.13" /></a><a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-24-green" alt="Node.js 24" /></a>
</h4>
<p align="center">
  <p align="center"><b>Production-Ready Serverless Synthetic Data Generator<br> <a href="https://huggingface.co/datasets/Hatman/plot-palette-100k"> Plot Palette Dataset » </a> </b> </p>
</p>
<h1 align="center">
  <img width="400" src="banner.png" alt="plot-palette icon">
</h1>
<p>Generate synthetic training data at scale using AWS Bedrock foundation models. Leverage ECS Fargate Spot instances for up to 70% cost savings with automatic checkpoint recovery. Configure jobs, upload seed data, and monitor progress through a modern React web interface.</p>
</div>

** THIS REPO IS IN ACTIVE DEVELOPMENT AND WILL CHANGE OFTEN **

## Structure

```text
├── frontend/   # React web application
├── backend/    # Lambda functions + ECS workers
├── docs/       # Documentation
└── tests/      # Centralized test suites
```

## Prerequisites

- **Node.js** v24 LTS (for frontend and scripts)
- **Python 3.13+** (for backend Lambda functions)
- **AWS CLI** configured with credentials (`aws configure`)
- **AWS SAM CLI** for serverless deployment

## Quick Start

```bash
npm install          # Install dependencies
npm run deploy       # Deploy backend to AWS
npm start            # Start frontend dev server
npm run check        # Run all lint and tests
```

## Deployment

```bash
npm run deploy
```

The deploy script prompts for configuration:

| Prompt | Description |
|--------|-------------|
| Stack Name | CloudFormation stack name (default: plot-palette) |
| AWS Region | Deployment region (default: us-east-1) |
| Environment | development or production |

Defaults are saved to `.env.deploy` and shown in brackets on subsequent runs.

See [docs/README.md](docs/README.md) for full documentation.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
