# Plot Palette v2 Feature Plans

## Overview

Plot Palette is a serverless synthetic data generation platform built on AWS. Users create Jinja2 prompt templates, upload seed data, configure budget limits, and launch generation jobs that run on ECS Fargate Spot instances with checkpoint-based recovery via S3 ETag concurrency control.

This plan set covers nine features that transform Plot Palette from a functional generation tool into a full experimentation and collaboration platform. The features span partial result export, template versioning with diff view, cost analytics, a template marketplace, job notifications, real-time progress streaming, batch job creation, seed data auto-generation, and automated output quality scoring.

Each phase is designed to fit within a single ~50k-token context window. Phases are sequential — each builds on infrastructure laid in previous phases. Phase 0 establishes shared conventions and architectural decisions that apply to all subsequent phases.

## Important

- Commit messages must NOT include `Co-Authored-By`, `Generated-By`, or any attribution lines.
- All commits must use conventional commit format: `type(scope): description`
- Valid scopes: `worker`, `lambdas`, `shared`, `frontend`, `infra`, `ci`, `docs`, `deps`

## Prerequisites

Before starting any phase, the engineer must have:

- **Node.js 24 LTS** (managed via nvm, see `.nvmrc`)
- **Python 3.13** (managed via uv, see `.python-version`)
- **uv** for Python package management (`uv pip install`, never bare `pip`)
- **AWS CLI** configured with dummy credentials for local testing
- **Docker** (for E2E tests with MiniStack)
- **Pre-commit** hooks installed (`pre-commit install`)

### Initial Setup

```bash
git clone <repo-url> && cd plot-palette
npm install                                              # Root + frontend deps
cd backend && uv pip install -e ".[dev,worker]" --system # Backend deps
cd ..
cp .env.example .env                                     # Fill in values
pre-commit install
```

### Verification Commands

```bash
npm run check                            # Full lint + test (frontend + backend)
npm run test:backend                     # Backend unit + integration tests
cd frontend && npx vitest run            # Frontend tests
cd frontend && npx vitest run --coverage # Frontend coverage (70% threshold)
```

## Phase Summary

| Phase | Goal | Features | Est. Tokens |
|-------|------|----------|-------------|
| [Phase 0](./Phase-0.md) | Foundation | ADRs, patterns, testing strategy, deployment conventions | ~15,000 |
| [Phase 1](./Phase-1.md) | Core Data Access | Partial Result Export, Template Version History + Diff View | ~45,000 |
| [Phase 2](./Phase-2.md) | Visibility & Sharing | Cost Analytics Dashboard, Template Marketplace | ~50,000 |
| [Phase 3](./Phase-3.md) | Real-Time & Notifications | Job Notifications (Email + Webhook), SSE Progress Streaming | ~50,000 |
| [Phase 4](./Phase-4.md) | Scale & Bootstrapping | Batch Job Creation, Seed Data Generation from Schema | ~50,000 |
| [Phase 5](./Phase-5.md) | Quality Feedback Loop | Automated Output Quality Scoring | ~40,000 |

## Dependency Graph

```
Phase 0 (Foundation)
  |
  v
Phase 1 (Partial Export + Version History)
  |
  v
Phase 2 (Cost Dashboard + Marketplace)
  |
  v
Phase 3 (Notifications + SSE)
  |
  v
Phase 4 (Batch Jobs + Seed Generation)
  |
  v
Phase 5 (Quality Scoring)
```

## Navigation

- [Phase 0: Foundation](./Phase-0.md)
- [Phase 1: Partial Result Export + Template Version History](./Phase-1.md)
- [Phase 2: Cost Analytics Dashboard + Template Marketplace](./Phase-2.md)
- [Phase 3: Job Notifications + Real-Time SSE Progress](./Phase-3.md)
- [Phase 4: Batch Job Creation + Seed Data Generation](./Phase-4.md)
- [Phase 5: Output Quality Scoring](./Phase-5.md)
