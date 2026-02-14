# Contributing to Plot Palette

## Prerequisites

- **Node.js 24** (via nvm)
- **Python 3.13** (via pyenv or system)
- **uv** — Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Docker** — for E2E tests (LocalStack)
- **pre-commit** — `uv pip install pre-commit` or `pipx install pre-commit`

## Getting Started

```bash
# Clone
git clone https://github.com/HatmanStack/plot-palette.git
cd plot-palette

# Frontend dependencies
npm install

# Backend dependencies
cd backend && uv pip install -e ".[dev,worker]" --system && cd ..

# Install pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Fill in your AWS credentials and Cognito config
```

## Running Tests

```bash
# All lint + tests (frontend + backend)
npm run check

# Frontend only
npm test

# Backend only
npm run test:backend

# E2E tests (requires Docker)
npm run test:e2e

# Single backend test file
PYTHONPATH=. pytest tests/unit/test_specific.py -v

# Single frontend test file
cd frontend && npx vitest run src/test/someFile.test.tsx
```

## Code Style

### Python (backend)

- **Linter**: ruff (E, W, F, I, B, C4 rules)
- **Type checker**: mypy (strict mode)
- **Line length**: 100 characters
- **Formatter**: ruff format

### TypeScript (frontend)

- **Linter**: ESLint with typescript-eslint
- **Type checker**: tsc --noEmit
- **Test framework**: Vitest + Testing Library

## PR Process

1. Branch from `main`
2. Make your changes
3. Run `npm run check` to verify lint + tests pass
4. Run `npm run test:e2e` if you modified backend code
5. Push and create a PR — the PR template will guide you
6. CI must pass before merge

## API Reference

See [`docs/openapi.yaml`](docs/openapi.yaml) for the OpenAPI specification covering all API endpoints.

## Branch Protection

See [`.github/branch-protection.md`](.github/branch-protection.md) for recommended branch protection rules and setup instructions.
