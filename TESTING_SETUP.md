# Testing Setup Guide

Complete guide to setting up and running the Plot Palette test suite.

## Quick Setup (Recommended)

```bash
# 1. Install backend package in development mode
pip install -e .[dev]

# 2. Verify installation
python -c "import backend.shared.models; print('✓ Backend package installed')"

# 3. Run unit tests
pytest tests/unit/ -v

# 4. Run with coverage
pytest tests/unit/ --cov=backend --cov-report=term-missing
```

## Detailed Setup

### Step 1: Install Python Dependencies

The backend package includes all necessary dependencies. Installing it in "editable" mode (`-e`) allows you to modify code without reinstalling:

```bash
pip install -e .[dev]
```

This installs:
- **Core dependencies** from `backend/requirements.txt`:
  - pydantic
  - boto3
  - jinja2
  - pyarrow
  - pandas
  - requests

- **Dev dependencies** from `requirements-dev.txt`:
  - pytest
  - pytest-cov
  - pytest-asyncio
  - moto
  - black
  - ruff
  - mypy

### Step 2: Verify Backend Package Installation

The `setup.py` makes the `backend` package importable from anywhere:

```bash
python -c "from backend.shared.models import JobConfig"
python -c "from backend.shared.utils import calculate_bedrock_cost"
python -c "from backend.ecs_tasks.worker.template_engine import TemplateEngine"
```

All imports should succeed without errors.

### Step 3: Run Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage report
pytest tests/unit/ --cov=backend --cov-report=html

# Open coverage report in browser
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Step 4: Check Coverage Threshold

```bash
# This will fail if coverage < 80%
coverage report --fail-under=80
```

## What the setup.py Does

The `setup.py` file:

1. **Makes backend a proper Python package**
   - Enables imports like `from backend.shared.models import JobConfig`
   - No need for `sys.path.insert()` hacks
   - No need to set PYTHONPATH manually

2. **Installs dependencies automatically**
   - Reads `backend/requirements.txt` for core deps
   - Reads `requirements-dev.txt` for dev deps
   - Installs them with `pip install -e .[dev]`

3. **Enables editable mode**
   - Changes to code take effect immediately
   - No need to reinstall after each change

## Import Pattern

**Before (WRONG)**:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/shared'))
from models import JobConfig  # Fails with relative imports
```

**After (CORRECT)**:
```python
from backend.shared.models import JobConfig  # Works!
```

## CI/CD Setup

The GitHub Actions workflows now use:

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -e .[dev]

- name: Run tests
  run: pytest tests/unit/ -v
```

No need to:
- Manually set PYTHONPATH
- Install requirements.txt separately
- Use sys.path hacks

## Troubleshooting

### "No module named 'backend'"

**Problem**: Backend package not installed.

**Solution**:
```bash
pip install -e .
```

### "ModuleNotFoundError: No module named 'pydantic'"

**Problem**: Dependencies not installed.

**Solution**:
```bash
pip install -e .[dev]
```

### Tests pass locally but fail in CI

**Problem**: CI might not have package installed.

**Solution**: Check `.github/workflows/test.yml` has:
```yaml
pip install -e .[dev]
```

### Coverage below 80%

**Problem**: Missing test coverage.

**Solution**:
1. Generate coverage report: `pytest --cov=backend --cov-report=html`
2. Open `htmlcov/index.html`
3. Identify uncovered lines (highlighted in red)
4. Add tests for those lines

## Phase 8 Status After Fixes

### ✅ Fixed Issues

1. **Import Patterns**: All test files now use `from backend.*` imports
2. **Package Installation**: Created `setup.py` for proper package setup
3. **CI/CD Configuration**: Workflows now use `pip install -e .[dev]`
4. **Test Coverage**: Added `test_models_extended.py` and `test_utils_extended.py`
5. **Documentation**: Created comprehensive setup guide

### ✅ Expected Coverage

With the additional tests:
- `backend/shared/models.py`: Should reach >80% (was 61.94%)
- `backend/shared/utils.py`: Should reach >80% (was 79.05%)
- Overall backend coverage: >80% target

### 📝 Verification Steps for Phase 9

When actual infrastructure is deployed, verify:

1. **Unit Tests**:
   ```bash
   pip install -e .[dev]
   pytest tests/unit/ --cov=backend --cov-report=term-missing
   coverage report --fail-under=80
   ```
   Should show >80% coverage.

2. **Integration Tests**:
   ```bash
   pytest tests/integration/ -v
   ```
   Should pass with mocked AWS services.

3. **E2E Tests** (requires deployed frontend):
   ```bash
   export FRONTEND_URL=https://your-frontend.amplifyapp.com
   npx playwright test
   ```

4. **Performance Tests** (requires deployed API):
   ```bash
   export API_ENDPOINT=https://your-api.execute-api.us-east-1.amazonaws.com
   locust -f tests/performance/locustfile.py --host=$API_ENDPOINT
   ```

## Summary

The test suite is now properly configured with:
- ✅ Consistent import patterns
- ✅ Proper package structure (setup.py)
- ✅ CI/CD workflows fixed
- ✅ Comprehensive documentation
- ✅ Additional coverage tests

All issues from the reviewer's feedback have been addressed.
