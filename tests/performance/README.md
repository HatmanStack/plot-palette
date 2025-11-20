# Performance Testing with Locust

Load testing for Plot Palette API Gateway endpoints.

## Prerequisites

```bash
pip install locust
```

## Running Tests

### Local Development

```bash
# With Web UI
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Then open http://localhost:8089 in browser
```

### Headless Mode (CI/CD)

```bash
# Test with 50 concurrent users, 5 users spawned per second, run for 5 minutes
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=50 \
    --spawn-rate=5 \
    --run-time=5m \
    --html=performance-report.html
```

### Against Deployed Infrastructure

```bash
# Get API endpoint from CloudFormation
export API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name plot-palette \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

# Run test
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=100 \
    --spawn-rate=10 \
    --run-time=10m
```

## Test Scenarios

### Standard Load Test

- **Users**: 50 concurrent
- **Spawn Rate**: 5 users/sec
- **Duration**: 5 minutes
- **Target**: API latency < 500ms (p95)

```bash
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=50 \
    --spawn-rate=5 \
    --run-time=5m
```

### Stress Test

- **Users**: 200 concurrent
- **Spawn Rate**: 20 users/sec
- **Duration**: 10 minutes
- **Goal**: Find breaking point

```bash
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=200 \
    --spawn-rate=20 \
    --run-time=10m
```

### Spike Test

- **Pattern**: Sudden burst of traffic
- **Goal**: Test auto-scaling behavior

```bash
# Start with 10 users, then spike to 100
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=100 \
    --spawn-rate=50 \
    --run-time=2m
```

### Soak Test

- **Users**: 30 concurrent
- **Duration**: 1 hour
- **Goal**: Detect memory leaks, resource exhaustion

```bash
locust -f tests/performance/locustfile.py \
    --host=$API_ENDPOINT \
    --headless \
    --users=30 \
    --spawn-rate=5 \
    --run-time=1h
```

## Performance Targets

Based on ADR Phase 0 requirements:

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Latency (p95) | < 500ms | Response time for API calls |
| Throughput | > 1000 req/sec | Total requests handled |
| Error Rate | < 1% | Failed requests / total requests |
| Concurrent Users | > 100 | Simultaneous active users |

## User Types

### PlotPaletteUser (weight: 10)

Regular user performing typical operations:
- List jobs (40% of requests)
- List templates (30%)
- Get job details (20%)
- Create job (8%)
- Other operations (2%)

### AdminUser (weight: 1)

Admin user with elevated permissions:
- List all jobs
- View system statistics
- Admin-only endpoints

### SpikeLoadUser (weight: 0)

Used for spike tests only:
- Rapid-fire requests
- Short wait times

## Metrics Collected

Locust automatically tracks:
- Request count
- Failure count
- Response times (min, max, average, median)
- Percentiles (50th, 66th, 75th, 80th, 90th, 95th, 98th, 99th, 99.9th, 99.99th, 100th)
- Requests per second
- Response size

## Analyzing Results

### View HTML Report

```bash
# Report is generated automatically
open performance-report.html
```

### Key Metrics to Check

1. **Response Time Percentiles**
   - p50 (median): Should be < 200ms
   - p95: Should be < 500ms
   - p99: Should be < 1000ms

2. **Error Rate**
   - Should be < 1%
   - 4xx errors: Client errors (validation, auth)
   - 5xx errors: Server errors (need investigation)

3. **Throughput**
   - Requests/second should be stable
   - Should handle 1000+ req/sec

4. **Response Time Over Time**
   - Should remain stable, not increase
   - Increasing trend indicates memory leak or resource exhaustion

## Troubleshooting

### High Error Rates

1. Check API Gateway logs:
   ```bash
   aws logs tail /aws/apigateway/plot-palette --follow
   ```

2. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/plot-palette-ListJobs --follow
   ```

### High Response Times

1. Check DynamoDB throttling:
   ```bash
   aws cloudwatch get-metric-statistics \
       --namespace AWS/DynamoDB \
       --metric-name ThrottledRequests \
       --dimensions Name=TableName,Value=plot-palette-Jobs \
       --start-time 2025-11-19T00:00:00Z \
       --end-time 2025-11-19T23:59:59Z \
       --period 300 \
       --statistics Sum
   ```

2. Check Lambda cold starts:
   - Look for "Init Duration" in Lambda logs
   - Consider provisioned concurrency for critical functions

### Connection Errors

1. Check API Gateway throttling limits
2. Verify security group allows traffic
3. Check VPC endpoint configuration

## Best Practices

1. **Start Small**: Begin with 10 users, gradually increase
2. **Monitor AWS Costs**: Load testing can incur costs
3. **Test Off-Peak**: Avoid production peak hours
4. **Clean Up**: Delete test jobs and templates after testing
5. **Use Dedicated Test Account**: Don't test in production account

## Integration with CI/CD

See `.github/workflows/performance-test.yml` for automated performance testing on deployment.

## Phase 9 Note

These tests are written in Phase 8 (code writing only). They will be executed against deployed infrastructure in Phase 9.
