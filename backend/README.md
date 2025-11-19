# Backend - Plot Palette

Python backend components for Plot Palette including shared libraries, Lambda functions, and ECS task definitions.

## Setup

### Prerequisites

- Python 3.13+
- pip or uv package manager

### Install Dependencies

From the project root:

```bash
# Using pip
cd backend
pip install -r requirements.txt

# Or using uv (recommended)
cd backend
uv pip install -r requirements.txt
```

### Verify Installation

Test that imports work correctly:

```bash
python3 -c "from backend.shared import JobConfig, JobStatus; print('✓ Backend shared library imports successfully')"
```

### Run Unit Tests

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests from project root
pytest tests/unit/test_shared.py -v

# Run with coverage
pytest tests/unit/test_shared.py -v --cov=backend/shared --cov-report=term-missing
```

## Project Structure

```
backend/
├── shared/              # Shared library for Lambda and ECS tasks
│   ├── __init__.py
│   ├── constants.py     # Application constants and pricing
│   ├── models.py        # Pydantic data models
│   └── utils.py         # Utility functions
├── lambdas/             # Lambda function handlers (Phase 3)
├── ecs_tasks/           # Fargate generation workers (Phase 4)
└── requirements.txt     # Python dependencies
```

## Shared Library

The `backend.shared` package provides:

- **Constants**: Job statuses, pricing, configuration values
- **Models**: Type-safe Pydantic models for Jobs, Templates, Checkpoints
- **Utilities**: ID generation, cost calculation, S3 operations, logging

### Example Usage

```python
from backend.shared import (
    JobConfig,
    JobStatus,
    generate_job_id,
    calculate_bedrock_cost,
)

# Generate a job ID
job_id = generate_job_id()

# Create a job configuration
job = JobConfig(
    job_id=job_id,
    user_id="user-123",
    status=JobStatus.QUEUED,
    config={"template_id": "template-1"},
    budget_limit=100.0,
)

# Calculate costs
cost = calculate_bedrock_cost(
    tokens=1_000_000,
    model_id="meta.llama3-1-8b-instruct-v1:0",
    is_input=True,
)
print(f"Cost for 1M input tokens: ${cost:.2f}")
```

## Development

### Code Standards

- **Formatting**: Black (line length 100)
- **Linting**: Ruff
- **Type Checking**: MyPy
- **Docstrings**: Google style

### Run Linters

```bash
# Format code
black backend/shared --line-length 100

# Lint code
ruff backend/shared

# Type check
mypy backend/shared
```

## Testing

Unit tests are located in `tests/unit/` and use pytest.

**Key test files:**
- `test_shared.py` - Tests for shared library (models, constants, utils)

**Running specific tests:**
```bash
# Test only models
pytest tests/unit/test_shared.py::TestJobConfig -v

# Test only utilities
pytest tests/unit/test_shared.py::TestUtilityFunctions -v
```

## Next Phases

- **Phase 3**: Lambda function handlers will be added to `backend/lambdas/`
- **Phase 4**: ECS Fargate task definitions will be added to `backend/ecs_tasks/`
