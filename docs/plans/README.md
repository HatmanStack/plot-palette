# Test Expansion Plan

Comprehensive test coverage expansion for Plot Palette - a serverless AWS application for synthetic training data generation using AWS Bedrock foundation models.

## Overview

This plan expands test coverage across the entire application to:
1. **Catch regressions** during active development
2. **Document expected behavior** through tests as living documentation

The expansion prioritizes **unit tests** with moderate mocking (external services + heavy dependencies), avoiding integration tests that require live AWS resources. All tests must pass in CI without cloud connectivity.

## Prerequisites

### Development Environment
- Node.js v24+ (managed via nvm)
- Python 3.13+ (managed via uv)
- Git

### Dependencies
```bash
# Frontend test dependencies (already installed)
cd frontend && npm install

# Backend test dependencies
cd backend && uv pip install -r requirements-dev.txt
```

### Test Commands
```bash
# Run all checks (lint + tests)
npm run check

# Frontend tests only
npm test

# Backend tests only
npm run test:backend

# Watch mode (frontend)
cd frontend && npm run test:watch

# Baseline coverage verification (backend)
PYTHONPATH=. pytest tests/ --cov=backend --cov-report=term-missing
```

## Phase Summary

| Phase | Goal | Token Estimate |
|-------|------|----------------|
| **Phase 0** | Foundation - Testing patterns, conventions, mocking strategies | ~8,000 |
| **Phase 1** | Frontend Tests - Hooks, contexts, key UI components | ~35,000 |
| **Phase 2** | Backend Tests - Lambda handlers, Worker/ECS failure scenarios | ~40,000 |

**Total Estimated Tokens:** ~83,000 (fits comfortably in two context windows)

## Navigation

- [Phase 0: Foundation](./Phase-0.md) - Architecture decisions, testing patterns, mocking strategies
- [Phase 1: Frontend Tests](./Phase-1.md) - React hooks, AuthContext, JobCard, TemplateCard, forms
- [Phase 2: Backend Tests](./Phase-2.md) - Lambda error handling, Worker failure recovery

## Test Coverage Targets

### Frontend (Currently: 0% | Target: ~70%)
| Component Type | Files | Priority |
|----------------|-------|----------|
| Hooks | `useAuth`, `useJobs`, `useJobPolling` | High |
| Contexts | `AuthContext`, `AuthProvider` | High |
| Components | `JobCard`, `StatusBadge`, `PrivateRoute` | Medium |
| Forms | `CreateJob`, `TemplateEditor` (key interactions) | Medium |

### Backend (Currently: ~60% | Target: ~80%)
| Component Type | Files | Priority |
|----------------|-------|----------|
| Lambda Handlers | Input validation, auth failures, AWS errors | High |
| Worker | Spot interruption, Bedrock failures, S3/DynamoDB errors | High |
| Shared Utils | Edge cases in cost calculation, validation | Medium |

## Architecture Decisions

See [Phase 0](./Phase-0.md) for detailed ADRs covering:
- ADR-001: Frontend testing with Vitest + React Testing Library
- ADR-002: Backend testing with pytest + moto for AWS mocking
- ADR-003: Moderate mocking strategy (external services + heavy dependencies)
- ADR-004: Test file organization mirroring source structure
