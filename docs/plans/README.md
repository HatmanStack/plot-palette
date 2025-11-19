# Plot Palette: AWS Full-Stack Synthetic Data Generator

## Feature Overview

This implementation plan transforms Plot Palette from a systemd-based Python script into a production-ready, serverless AWS application that generates synthetic training data using AWS Bedrock foundation models. The system leverages ECS Fargate Spot instances to opportunistically consume spare compute capacity at significantly reduced costs (up to 70% savings), with robust checkpoint-based recovery for spot interruptions.

Users interact with a modern React web application to configure generation jobs, upload seed data, customize prompt templates, and monitor real-time progress with cost tracking. The architecture is fully serverless (except for the generation workers), with automatic scaling, multi-region support, and one-click CloudFormation deployment. Generated datasets are exported in multiple formats (JSONL, Parquet, CSV) and automatically archived to Glacier after 3 days while preserving metadata for historical tracking.

The system implements sophisticated features including smart model routing (using cost-efficient models for question generation and premium models for answers), a flexible prompt template engine supporting multi-step generation flows with conditional logic, automatic schema detection from templates, concurrent job execution with DynamoDB-based queuing, and hard budget limits to prevent runaway costs. All AWS resources are deployed via nested CloudFormation stacks for modularity and maintainability.

## ⚠️ Important: Phased Implementation Approach

**Each phase is implemented in a separate context/session.**

### Implementation Strategy

**Phases 1-8: CODE WRITING ONLY**
- Write CloudFormation templates, Lambda functions, React components, etc.
- Create all infrastructure-as-code definitions
- Build test files and documentation
- **DO NOT deploy any AWS resources**
- **DO NOT run tests that require AWS infrastructure**
- Focus on completing the codebase

**Phase 9: DEPLOYMENT & VERIFICATION**
- Deploy all CloudFormation stacks to AWS
- Run integration tests against deployed resources
- Execute end-to-end tests
- Verify system functionality
- Complete production deployment

### Why This Approach?

1. **Separation of Concerns:** Code writing doesn't require AWS costs
2. **Cost Control:** No AWS charges until you're ready to deploy
3. **Iterative Development:** Review all code before committing to infrastructure
4. **Context Management:** Each phase fits in a single implementation context (75K-110K tokens)

### What This Means for Each Phase

**During Phases 1-8:**
- Follow implementation steps to write code
- Create all files and templates as specified
- Commit code after each task
- Skip any "Testing Instructions" that require deployed AWS resources
- Ignore "Run this command to verify" sections that need real infrastructure

**During Phase 9:**
- Deploy everything using the CloudFormation master stack
- Run all deferred tests and verification steps
- Execute smoke tests and integration tests
- Validate the complete system end-to-end

## Prerequisites

### Required Tools & Accounts
- AWS Account with appropriate permissions (Administrator or PowerUser)
- AWS CLI v2+ configured with credentials
- Python 3.13+ installed locally for development
- Node.js 20+ and npm for frontend development
- Git for version control
- Docker (optional, for local testing of ECS tasks)

### Required AWS Service Quotas
- AWS Bedrock access enabled in target region (request model access in console)
- ECS Fargate Spot capacity available
- Cognito User Pool quota available
- S3 bucket creation quota

### Development Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd plot-palette

# Python virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### Knowledge Prerequisites
- Familiarity with AWS CloudFormation
- Python 3.13 async/await patterns
- React functional components and hooks
- REST API design
- Docker containerization basics
- AWS IAM security model

## Phase Summary

| Phase | Goal | Est. Tokens | Dependencies |
|-------|------|-------------|--------------|
| [Phase 0](./Phase-0.md) | Architecture & Design Foundation | Reference Only | None |
| [Phase 1](./Phase-1.md) | Core Infrastructure Setup | ~95,000 | Phase 0 |
| [Phase 2](./Phase-2.md) | Authentication & API Gateway | ~88,000 | Phase 1 |
| [Phase 3](./Phase-3.md) | Backend APIs & Job Management | ~102,000 | Phase 2 |
| [Phase 4](./Phase-4.md) | ECS Fargate Generation Workers | ~98,000 | Phase 3 |
| [Phase 5](./Phase-5.md) | Prompt Template Engine | ~105,000 | Phase 4 |
| [Phase 6](./Phase-6.md) | React Frontend Application | ~110,000 | Phase 5 |
| [Phase 7](./Phase-7.md) | CloudFormation Nested Stacks | ~95,000 | Phase 6 |
| [Phase 8](./Phase-8.md) | Integration Testing & E2E | ~75,000 | Phase 7 |
| [Phase 9](./Phase-9.md) | Documentation & Deployment | ~45,000 | Phase 8 |

**Token estimates are per-phase.** Each phase is designed to fit comfortably within a single implementation context (200K token limit) with room for conversation and iteration.

**Total Codebase:** ~813,000 tokens across all phases (code writing only, deployment happens in Phase 9)

## Navigation

- **Start Here:** [Phase-0.md](./Phase-0.md) - Review architecture decisions and design rationale
- **Implementation:** Follow phases sequentially (Phase-1 → Phase-9)
- **Each phase:** Self-contained with clear prerequisites and verification steps

## Development Workflow

### For Each Phase (1-8)

1. **Read Phase-0** completely before starting Phase 1
2. **Start a new implementation context** for each phase
3. **Follow task order** within the phase
4. **Create all files** as specified in implementation steps
5. **Write all code** - CloudFormation templates, Lambda functions, React components, tests, etc.
6. **Commit after each task** using provided commit message templates
7. **DO NOT deploy to AWS** - this is code writing only
8. **DO NOT run tests** that require deployed infrastructure
9. **Complete the phase** by writing all code specified
10. **Move to next phase** in a fresh context

### For Phase 9 (Deployment & Verification)

1. **Start deployment phase** with all code from Phases 1-8 complete
2. **Deploy CloudFormation stacks** to AWS following deployment scripts
3. **Run all integration tests** against deployed infrastructure
4. **Execute verification steps** from previous phases
5. **Validate system** end-to-end with smoke tests
6. **Complete documentation** with production URLs and credentials
7. **Production go-live** following final checklist

## Success Criteria

The implementation is complete when:

- [ ] One-click CloudFormation deployment creates all infrastructure
- [ ] Users can authenticate via Cognito and access web UI
- [ ] Users can upload seed data and create custom prompt templates
- [ ] Generation jobs execute on Fargate Spot with checkpoint recovery
- [ ] Dashboard shows real-time progress and cost tracking
- [ ] Generated datasets export in multiple formats
- [ ] Budget limits halt jobs automatically
- [ ] Data archives to Glacier after 3 days
- [ ] All integration tests pass
- [ ] Documentation is complete and accurate

## Key Design Decisions

See [Phase-0.md](./Phase-0.md) for detailed architecture decisions including:

- Why ECS Fargate Spot over Kubernetes
- Custom VPC vs default VPC rationale
- Bedrock model selection strategy
- Prompt template engine design
- Cost tracking implementation approach
- Security and IAM model

## Support & Questions

If implementation questions arise:
1. Check Phase-0 architecture decisions first
2. Review task prerequisites and verification steps
3. Consult AWS documentation for service-specific questions
4. Ensure all previous phase verification steps passed

---

**Ready to begin?** → Start with [Phase-0.md](./Phase-0.md)
