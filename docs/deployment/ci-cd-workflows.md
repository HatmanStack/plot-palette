# GitHub Actions CI/CD Workflows

Automated testing and deployment pipelines for Plot Palette.

## Workflows

### 1. Test Suite (`test.yml`)

**Trigger**: Push to `main` or `develop`, Pull Requests

**Jobs**:
- **unit-tests**: Run pytest unit tests with coverage (target: 80%)
- **integration-tests**: Run integration tests (requires AWS credentials)
- **frontend-tests**: Run frontend linting, type checking, and tests
- **code-quality**: Black formatting, Ruff linting, mypy type checking
- **security-scan**: Trivy vulnerability scanner, Python safety checks
- **test-summary**: Aggregate results from all test jobs

**Required Secrets**:
- `AWS_ACCESS_KEY_ID` (for integration tests)
- `AWS_SECRET_ACCESS_KEY` (for integration tests)
- `CODECOV_TOKEN` (optional, for coverage reporting)

**Artifacts**:
- Coverage HTML report (7 days retention)
- Coverage XML for Codecov

---

### 2. Deployment (`deploy.yml`)

**Trigger**: Git tags (`v*`), Manual workflow dispatch

**Jobs**:
- **pre-deploy-checks**: Validate templates and run unit tests
- **deploy-infrastructure**: Deploy CloudFormation stacks
- **deploy-frontend**: Build and deploy frontend to Amplify
- **smoke-tests**: Basic health checks on deployed services
- **notify-deployment**: Create GitHub release and notify status

**Required Secrets**:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (default: us-east-1)
- `DEPLOYMENT_BUCKET` (S3 bucket for Lambda packages)
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`

**Manual Deployment**:
```bash
# From GitHub UI: Actions > Deploy to AWS > Run workflow
# Select environment: staging or production
```

**Tag-based Deployment**:
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

### 3. E2E Tests (`e2e-tests.yml`)

**Trigger**: Daily schedule (2 AM UTC), Manual workflow dispatch

**Jobs**:
- **e2e-tests**: Run Playwright tests against deployed environment
- **visual-regression**: Visual diff tests (snapshots)
- **notify-results**: Summarize test results

**Required Secrets**:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `TEST_USER_EMAIL` (Cognito test user)
- `TEST_USER_PASSWORD`

**Artifacts**:
- Playwright HTML report
- Test videos (on failure)
- Visual diffs (on failure)

**Manual Run**:
```bash
# From GitHub UI: Actions > E2E Tests > Run workflow
# Select environment: staging or production
```

---

### 4. Performance Tests (`performance-test.yml`)

**Trigger**: Manual workflow dispatch only

**Jobs**:
- **load-test**: Run Locust load test with configurable users and duration
- **stress-test**: Run stress test with 200 concurrent users
- **notify-results**: Performance test summary

**Required Secrets**:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

**Parameters**:
- `environment`: staging or production
- `users`: Number of concurrent users (default: 50)
- `duration`: Test duration (default: 5m)

**Manual Run**:
```bash
# From GitHub UI: Actions > Performance Tests > Run workflow
# Configure parameters:
#   - Environment: staging
#   - Users: 50
#   - Duration: 5m
```

**Thresholds**:
- P95 response time < 500ms
- Error rate < 1%

**Artifacts**:
- Performance HTML report (30 days retention)
- CSV results with detailed metrics

---

## Setup Instructions

### 1. Configure AWS Credentials

Add the following secrets to your GitHub repository:

```
Settings > Secrets and variables > Actions > New repository secret
```

Required secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `DEPLOYMENT_BUCKET`

### 2. Create Deployment Bucket

```bash
aws s3 mb s3://plot-palette-deployment-artifacts
```

Add to GitHub secrets:
```
DEPLOYMENT_BUCKET=plot-palette-deployment-artifacts
```

### 3. Set Up Cognito Test User

Create a test user in Cognito User Pool:

```bash
aws cognito-idp admin-create-user \
    --user-pool-id <pool-id> \
    --username test@example.com \
    --user-attributes Name=email,Value=test@example.com \
    --temporary-password "TempPassword123!"

# Set permanent password
aws cognito-idp admin-set-user-password \
    --user-pool-id <pool-id> \
    --username test@example.com \
    --password "TestPassword123!" \
    --permanent
```

Add to GitHub secrets:
```
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=TestPassword123!
```

### 4. Configure Codecov (Optional)

Sign up at https://codecov.io/ and add:
```
CODECOV_TOKEN=<your-token>
```

---

## Workflow Status Badges

Add to your README.md:

```markdown
![Test Suite](https://github.com/yourusername/plot-palette/workflows/Test%20Suite/badge.svg)
![Deploy to AWS](https://github.com/yourusername/plot-palette/workflows/Deploy%20to%20AWS/badge.svg)
![E2E Tests](https://github.com/yourusername/plot-palette/workflows/E2E%20Tests/badge.svg)
```

---

## Development Workflow

### Feature Development

1. Create feature branch from `develop`
2. Make changes
3. Push to GitHub
4. **Automated**: Test Suite runs on PR
5. Review test results
6. Merge to `develop`

### Release Process

1. Merge `develop` to `main`
2. Tag release: `git tag v1.0.0`
3. Push tag: `git push origin v1.0.0`
4. **Automated**: Deployment workflow runs
5. **Automated**: E2E tests run against staging
6. Manual approval for production deployment

---

## Troubleshooting

### Test Suite Failures

**Unit tests failing:**
- Check coverage report artifact
- Ensure all tests pass locally: `pytest tests/unit/ -v`

**Integration tests failing:**
- Verify AWS credentials are valid
- Check AWS service quotas
- Review CloudWatch logs

**Frontend tests failing:**
- Check linter output
- Run locally: `cd frontend && npm test`

### Deployment Failures

**CloudFormation errors:**
- Check CloudFormation events in AWS Console
- Validate template locally: `aws cloudformation validate-template`

**Lambda deployment errors:**
- Verify Lambda package size < 50MB
- Check IAM permissions

**Frontend deployment errors:**
- Verify Amplify configuration
- Check build logs in Amplify Console

### E2E Test Failures

**Playwright errors:**
- Check test videos artifact
- Review screenshots
- Verify frontend URL is accessible

**Authentication errors:**
- Verify Cognito test user exists
- Check user password hasn't expired

### Performance Test Failures

**High response times:**
- Check API Gateway CloudWatch metrics
- Review Lambda function duration
- Check DynamoDB throttling

**High error rates:**
- Review API Gateway logs
- Check Lambda function errors
- Verify rate limits

---

## Cost Optimization

### GitHub Actions Minutes

- Free tier: 2,000 minutes/month (public repos)
- Private repos: 2,000-50,000 minutes/month (depending on plan)

**Tips**:
- Use `if` conditions to skip unnecessary jobs
- Cache dependencies (`actions/cache`)
- Run expensive tests (E2E, performance) on schedule or manual trigger

### AWS Costs

- **Integration tests**: Minimal (mocked services with moto)
- **E2E tests**: ~$0.10-0.50 per run
- **Performance tests**: ~$1-5 per run (depends on duration)
- **Deployments**: Free (existing infrastructure)

**Cost Control**:
- Run performance tests sparingly
- Use staging environment for testing
- Clean up test data after runs

---

## Security Best Practices

1. **Never commit secrets** to repository
2. **Use GitHub Secrets** for sensitive data
3. **Rotate AWS credentials** regularly
4. **Use least-privilege IAM policies**
5. **Enable security scanning** (Trivy, safety)
6. **Review and approve** production deployments manually

---

## Support

For issues with GitHub Actions workflows:
1. Check workflow run logs
2. Review this documentation
3. Open issue in repository

For AWS-specific issues:
- Check CloudWatch logs
- Review CloudFormation events
- Consult AWS documentation
