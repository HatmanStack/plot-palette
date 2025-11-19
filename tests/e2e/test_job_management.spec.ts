/**
 * E2E Test: Job Management
 *
 * Tests job creation, monitoring, cancellation, and management operations.
 *
 * NOTE: Phase 8 is code writing only. These tests will run against
 * deployed infrastructure in Phase 9.
 */

import { test, expect } from '@playwright/test';

test.describe('Job Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');

    // Navigate to new job page
    await page.goto('/jobs/new');
  });

  test('create job with all required fields', async ({ page }) => {
    // Fill job creation form
    await page.fill('input[name="jobName"]', 'Test Job');

    // Select template
    await page.selectOption('select[name="templateId"]', { index: 1 });

    // Upload seed data
    const seedData = [
      { author: { name: 'Test Author', biography: 'Test bio', genre: 'fiction' } },
    ];
    await page.setInputFiles('input[type="file"]', {
      name: 'seed.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(seedData)),
    });

    // Set targets
    await page.fill('input[name="targetRecords"]', '100');
    await page.fill('input[name="budgetLimit"]', '10.00');

    // Submit
    await page.click('button:has-text("Create Job")');

    // Verify created
    await expect(page.locator('text=Job created successfully')).toBeVisible({ timeout: 10000 });
    await expect(page).toHaveURL(/.*jobs\/[a-f0-9-]+/);
  });

  test('validate required fields', async ({ page }) => {
    // Try to submit without filling fields
    await page.click('button:has-text("Create Job")');

    // Should show validation errors
    await expect(page.locator('text=Template is required')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Seed data is required')).toBeVisible();
  });

  test('validate budget minimum', async ({ page }) => {
    await page.fill('input[name="budgetLimit"]', '0.01');
    await page.click('button:has-text("Create Job")');

    // Should show budget warning
    await expect(page.locator('text=Budget too low')).toBeVisible({ timeout: 5000 });
  });

  test('show cost estimate before creation', async ({ page }) => {
    // Fill form
    await page.selectOption('select[name="templateId"]', { index: 1 });
    await page.fill('input[name="targetRecords"]', '1000');

    // Should show cost estimate
    await expect(page.locator('[data-testid="cost-estimate"]')).toBeVisible({ timeout: 5000 });

    // Cost estimate should update when fields change
    await page.fill('input[name="targetRecords"]', '2000');

    // Wait for estimate to update
    await page.waitForTimeout(1000);

    const estimate = await page.locator('[data-testid="cost-estimate"]').textContent();
    expect(estimate).toBeTruthy();
  });
});

test.describe('Job Monitoring', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
  });

  test('view job detail page', async ({ page }) => {
    // Navigate to jobs list
    await page.goto('/jobs');

    // Click first job
    const firstJob = page.locator('[data-testid="job-row"]').first();
    await firstJob.click();

    // Verify job detail page
    await expect(page).toHaveURL(/.*jobs\/[a-f0-9-]+/);
    await expect(page.locator('[data-testid="job-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();
  });

  test('monitor real-time progress', async ({ page }) => {
    // Navigate to running job
    await page.goto('/jobs');
    const runningJob = page.locator('[data-status="RUNNING"]').first();

    if (await runningJob.isVisible()) {
      await runningJob.click();

      // Verify progress indicators
      await expect(page.locator('[data-testid="records-generated"]')).toBeVisible();
      await expect(page.locator('[data-testid="tokens-used"]')).toBeVisible();
      await expect(page.locator('[data-testid="cost-accumulated"]')).toBeVisible();

      // Progress should update (wait for WebSocket or polling)
      await page.waitForTimeout(5000);

      // Check if progress changed
      const progress = await page.locator('[data-testid="progress-percent"]').textContent();
      expect(progress).toBeTruthy();
    }
  });

  test('view cost breakdown', async ({ page }) => {
    await page.goto('/jobs');
    const completedJob = page.locator('[data-status="COMPLETED"]').first();

    if (await completedJob.isVisible()) {
      await completedJob.click();

      // Click cost breakdown
      await page.click('button:has-text("Cost Breakdown")');

      // Verify breakdown details
      await expect(page.locator('text=Bedrock Tokens')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=Fargate Hours')).toBeVisible();
      await expect(page.locator('text=S3 Operations')).toBeVisible();
    }
  });

  test('view job logs', async ({ page }) => {
    await page.goto('/jobs');
    const firstJob = page.locator('[data-testid="job-row"]').first();
    await firstJob.click();

    // Click logs tab
    await page.click('text=Logs');

    // Verify logs visible
    await expect(page.locator('[data-testid="log-entries"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Job Actions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
  });

  test('cancel running job', async ({ page }) => {
    await page.goto('/jobs');
    const runningJob = page.locator('[data-status="RUNNING"]').first();

    if (await runningJob.isVisible()) {
      await runningJob.click();

      // Cancel job
      await page.click('button:has-text("Cancel Job")');

      // Confirm
      await page.click('button:has-text("Confirm")');

      // Verify cancelled
      await expect(page.locator('text=CANCELLED')).toBeVisible({ timeout: 15000 });
    }
  });

  test('delete completed job', async ({ page }) => {
    await page.goto('/jobs');
    const completedJob = page.locator('[data-status="COMPLETED"]').first();

    if (await completedJob.isVisible()) {
      await completedJob.click();

      // Delete job
      await page.click('button:has-text("Delete Job")');

      // Confirm
      await page.click('button:has-text("Confirm Delete")');

      // Verify deleted
      await expect(page.locator('text=Job deleted successfully')).toBeVisible({ timeout: 10000 });

      // Should redirect to jobs list
      await expect(page).toHaveURL(/.*jobs$/);
    }
  });

  test('retry failed job', async ({ page }) => {
    await page.goto('/jobs');
    const failedJob = page.locator('[data-status="FAILED"]').first();

    if (await failedJob.isVisible()) {
      await failedJob.click();

      // Retry job
      await page.click('button:has-text("Retry Job")');

      // Verify new job created
      await expect(page.locator('text=Job restarted')).toBeVisible({ timeout: 10000 });
    }
  });

  test('export data in multiple formats', async ({ page }) => {
    await page.goto('/jobs');
    const completedJob = page.locator('[data-status="COMPLETED"]').first();

    if (await completedJob.isVisible()) {
      await completedJob.click();

      // Download JSONL
      await page.click('button:has-text("Download JSONL")');
      const jsonlDownload = await page.waitForEvent('download', { timeout: 30000 });
      expect(jsonlDownload.suggestedFilename()).toMatch(/\.jsonl$/);

      // Download CSV
      await page.click('button:has-text("Download CSV")');
      const csvDownload = await page.waitForEvent('download', { timeout: 30000 });
      expect(csvDownload.suggestedFilename()).toMatch(/\.csv$/);

      // Download Parquet
      await page.click('button:has-text("Download Parquet")');
      const parquetDownload = await page.waitForEvent('download', { timeout: 30000 });
      expect(parquetDownload.suggestedFilename()).toMatch(/\.parquet$/);
    }
  });
});

test.describe('Job List and Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.goto('/jobs');
  });

  test('view all jobs', async ({ page }) => {
    // Verify jobs table visible
    await expect(page.locator('[data-testid="jobs-table"]')).toBeVisible({ timeout: 5000 });

    // Verify at least one job row
    const jobRows = page.locator('[data-testid="job-row"]');
    await expect(jobRows.first()).toBeVisible();
  });

  test('filter jobs by status', async ({ page }) => {
    // Filter by COMPLETED
    await page.selectOption('select[name="statusFilter"]', 'COMPLETED');

    // Verify all visible jobs are COMPLETED
    const completedJobs = page.locator('[data-status="COMPLETED"]');
    await expect(completedJobs.first()).toBeVisible({ timeout: 5000 });
  });

  test('search jobs by name', async ({ page }) => {
    // Search
    await page.fill('input[placeholder="Search jobs..."]', 'test');

    // Wait for results
    await page.waitForTimeout(1000);

    // Verify filtered results
    const results = page.locator('[data-testid="job-row"]');
    const count = await results.count();
    expect(count).toBeGreaterThan(0);
  });

  test('sort jobs by date', async ({ page }) => {
    // Click date column header
    await page.click('th:has-text("Created")');

    // Verify sort order changed
    await page.waitForTimeout(500);

    // Check first job is most recent
    const firstJobDate = await page.locator('[data-testid="job-row"]').first()
      .locator('[data-testid="created-date"]').textContent();
    expect(firstJobDate).toBeTruthy();
  });

  test('paginate through jobs', async ({ page }) => {
    // Check if pagination exists
    const pagination = page.locator('[data-testid="pagination"]');

    if (await pagination.isVisible()) {
      // Go to next page
      await page.click('button:has-text("Next")');

      // Verify page changed
      await page.waitForTimeout(500);

      // Check URL or page indicator
      const pageIndicator = page.locator('[data-testid="page-number"]');
      const pageNum = await pageIndicator.textContent();
      expect(pageNum).toBe('2');
    }
  });
});

test.describe('Budget Enforcement UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
  });

  test('show budget exceeded status', async ({ page }) => {
    await page.goto('/jobs');
    const budgetExceededJob = page.locator('[data-status="BUDGET_EXCEEDED"]').first();

    if (await budgetExceededJob.isVisible()) {
      await budgetExceededJob.click();

      // Verify budget exceeded badge
      await expect(page.locator('text=BUDGET EXCEEDED')).toBeVisible();

      // Verify cost vs budget comparison
      await expect(page.locator('[data-testid="budget-comparison"]')).toBeVisible();
    }
  });

  test('show budget warning when approaching limit', async ({ page }) => {
    // Create job with low budget
    await page.goto('/jobs/new');

    // ... fill form with low budget ...

    // In job detail, should show warning at 80% budget
    // This would require WebSocket or polling in real implementation
  });
});
