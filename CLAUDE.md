# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
npm install                                              # Frontend deps
cd backend && uv pip install -e ".[dev,worker]" --system # Backend deps
cp .env.example .env                                     # Fill in AWS/Cognito values
pre-commit install                                       # Hooks: ruff, ruff-format, eslint, trailing-whitespace, detect-private-key
```

## Build & Development Commands

### Frontend (React 19 + Vite + TypeScript)

```bash
npm run dev                              # Start Vite dev server
npm run build                            # TypeScript compile + Vite build
npm run lint                             # ESLint + tsc --noEmit
npm run test                             # Vitest (all frontend tests)
cd frontend && npx vitest run src/test/someFile.test.tsx  # Single test file
cd frontend && npx vitest --watch        # Watch mode
```

### Backend (Python 3.13)

```bash
npm run lint:backend                     # Ruff lint (runs from backend/)
npm run test:backend                     # Pytest unit + integration tests
PYTHONPATH=. pytest tests/unit/test_specific.py -v       # Single test file
PYTHONPATH=. pytest tests/unit/test_specific.py::test_fn # Single test function
```

### E2E Tests (requires Docker)

```bash
npm run test:e2e                         # Spins up LocalStack, runs tests, tears down
```

### Full Check

```bash
npm run check                            # All linting + all tests (frontend + backend)
```

### CI-Equivalent Local Commands

CI runs additional checks not covered by `npm run check`:

```bash
cd backend && mypy shared/ lambdas/ --config-file pyproject.toml  # Type check (non-blocking in CI)
bandit -r backend/ -ll -ii --exclude tests                        # Security scan
cfn-lint backend/template.yaml                                    # CloudFormation lint
```

**Important:** Backend tests require `PYTHONPATH=.` set at the repo root. CI also sets `AWS_DEFAULT_REGION=us-east-1` with dummy AWS credentials for moto mocking.

## Architecture

Serverless synthetic data generation platform using AWS Bedrock LLMs to generate training data at scale.

### Backend (`backend/`)

**Lambda functions** (`backend/lambdas/`) — 16 API handlers for CRUD on jobs, templates, seed data, and dashboard stats. Each Lambda is a standalone handler file. All share the common modules below. Lambda files have an E402 ruff exemption (imports after sys.path manipulation).

**Shared modules** (`backend/shared/`) — The core business logic layer:

- `models.py` — Pydantic models (`JobConfig`, `TemplateDefinition`, `CheckpointState`, `CostBreakdown`, `QueueItem`) with DynamoDB serialization
- `constants.py` — Enums (`JobStatus`, `ExportFormat`), model pricing tables, Fargate Spot pricing, tier-to-model mapping (tier-1=cheap/Llama 8B, tier-2=balanced/Llama 70B, tier-3=premium/Claude 3.5 Sonnet)
- `utils.py` — Cost calculation, token estimation, S3 helpers, validation
- `aws_clients.py` — AWS client factory
- `retry.py` — Exponential backoff retry logic
- `template_filters.py` — Custom Jinja2 filters for prompt templates

**ECS worker** (`backend/ecs_tasks/worker/`) — Long-running Fargate Spot task that processes generation jobs. Uses checkpoint-based recovery for Spot interruptions with SIGTERM handling and S3 ETag concurrency control.

**Infrastructure** (`backend/infrastructure/`) — CloudFormation nested stacks + SAM template (`backend/template.yaml`). DynamoDB tables: Jobs, Queue, Templates, CostTracking, CheckpointMetadata. Step Functions state machine for job lifecycle orchestration. Deploy scripts in `backend/infrastructure/scripts/`.

### Frontend (`frontend/`)

React 19 SPA with React Router, React Query for server state, Cognito auth, Monaco editor for template editing, Tailwind CSS styling.

- `src/routes/` — Page components (Dashboard, Jobs, Templates, Settings, Login)
- `src/contexts/AuthContext` — Cognito authentication state
- `src/hooks/` — `useAuth`, `useJobs`, `useJobPolling`
- `src/services/` — API client (axios) and auth service wrappers

### Tests (`tests/`)

Backend tests live at the repo root in `tests/` (not inside `backend/`). Uses `moto[all]` for AWS mocking. Frontend tests live in `frontend/src/test/`. Pytest markers: `unit`, `integration`, `worker`, `slow`.

Test fixtures are layered: `tests/conftest.py` (mock AWS clients, env vars) > `tests/unit/conftest.py` (sample models) > `tests/integration/conftest.py` (Cognito, real boto3) > `tests/e2e/conftest.py` (LocalStack provisioning, Lambda import shims).

Coverage requirement: 70% (backend via pytest-cov, frontend via vitest/v8).

## Code Style

- **Python:** Ruff linter + formatter (E, W, F, I, B, C4 rules), 100-char line length, target py311. Known first-party imports: `shared`, `lambdas`, `ecs_tasks`. Mypy strict mode configured.
- **TypeScript:** ESLint 9 flat config with typescript-eslint, React hooks plugin. Vitest + Testing Library for tests.
- **Python packaging:** Always use `uv pip install` / `uvx` (never bare `pip`).
