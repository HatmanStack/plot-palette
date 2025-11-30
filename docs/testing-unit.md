# Unit Tests

Unit tests for Lambda functions and backend logic that don't require deployed AWS infrastructure.

## Running Tests

### Run All Unit Tests

```bash
pytest tests/unit/ -v
```

### Run Specific Test Files

```bash
# Health check Lambda tests
pytest tests/unit/test_health.py -v

# User info Lambda tests
pytest tests/unit/test_user.py -v

# Shared library tests
pytest tests/unit/test_shared.py -v
```

### Run with Coverage

```bash
pytest tests/unit/ --cov=backend --cov-report=html
```

### Run with Output

```bash
pytest tests/unit/ -v -s
```

## Test Files

- `test_health.py` - Unit tests for health check Lambda function
- `test_user.py` - Unit tests for user info Lambda function
- `test_shared.py` - Unit tests for shared backend library (from Phase 1)
- `README.md` - This file

## Notes

- Unit tests use mock objects and don't make actual AWS API calls
- No AWS credentials or deployed infrastructure required
- Tests should run quickly (< 1 second per test)
- All Lambda handler code is tested in isolation
