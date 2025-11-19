/**
 * E2E Test: Complete User Workflow
 *
 * Tests the full user journey from signup to data export:
 * 1. User registration
 * 2. Login
 * 3. Template creation
 * 4. Seed data upload
 * 5. Job creation with budget
 * 6. Progress monitoring
 * 7. Data export download
 *
 * NOTE: Phase 8 is code writing only. These tests will run against
 * deployed infrastructure in Phase 9.
 */

import { test, expect } from '@playwright/test';

// Test data
const testUser = {
  email: `test-${Date.now()}@example.com`,
  password: 'TestPassword123!',
};

const testTemplate = {
  name: 'E2E Test Template',
  prompt: `Generate a creative story about {{ author.name }}.

Author biography: {{ author.biography }}

Write a compelling narrative.`,
};

const testJob = {
  name: 'E2E Test Job',
  targetRecords: 10,
  budgetLimit: 5.0,
};

test.describe('Complete User Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Start at home page
    await page.goto('/');
  });

  test('complete workflow: signup to data export', async ({ page }) => {
    // Step 1: Navigate to signup
    await page.click('text=Sign Up');
    await expect(page).toHaveURL(/.*signup/);

    // Step 2: Fill signup form
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);
    await page.fill('input[name="confirmPassword"]', testUser.password);
    await page.click('button[type="submit"]');

    // Wait for verification message
    await expect(page.locator('text=Verify your email')).toBeVisible({ timeout: 10000 });

    // Note: In real test, would need email verification
    // For now, simulate manual verification or use test Cognito user

    // Step 3: Login
    await page.goto('/login');
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 15000 });

    // Step 4: Create template
    await page.click('text=Templates');
    await expect(page).toHaveURL(/.*templates/);

    await page.click('button:has-text("New Template")');
    await page.fill('input[name="name"]', testTemplate.name);
    await page.fill('textarea[name="prompt"]', testTemplate.prompt);
    await page.click('button:has-text("Save Template")');

    // Verify template created
    await expect(page.locator(`text=${testTemplate.name}`)).toBeVisible({ timeout: 10000 });

    // Step 5: Navigate to new job creation
    await page.click('text=Jobs');
    await page.click('button:has-text("New Job")');

    // Step 6: Fill job creation form
    await page.fill('input[name="jobName"]', testJob.name);

    // Select template
    await page.click('select[name="templateId"]');
    await page.selectOption('select[name="templateId"]', { label: testTemplate.name });

    // Upload seed data (mock file)
    const seedData = [
      {
        author: {
          name: 'Jane Doe',
          biography: 'A prolific writer known for poetic narratives.',
        },
      },
      {
        author: {
          name: 'John Smith',
          biography: 'An acclaimed author of historical fiction.',
        },
      },
    ];

    // Create file upload
    const fileContent = JSON.stringify(seedData);
    await page.setInputFiles('input[type="file"]', {
      name: 'seed-data.json',
      mimeType: 'application/json',
      buffer: Buffer.from(fileContent),
    });

    // Set target records and budget
    await page.fill('input[name="targetRecords"]', testJob.targetRecords.toString());
    await page.fill('input[name="budgetLimit"]', testJob.budgetLimit.toString());

    // Submit job
    await page.click('button:has-text("Create Job")');

    // Step 7: Monitor job progress
    await expect(page.locator('text=Job created successfully')).toBeVisible({ timeout: 10000 });

    // Should redirect to job detail page
    await expect(page).toHaveURL(/.*jobs\/[a-f0-9-]+/);

    // Verify job status
    const statusBadge = page.locator('[data-testid="job-status"]');
    await expect(statusBadge).toBeVisible({ timeout: 5000 });

    // Check progress indicators
    await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();
    await expect(page.locator('[data-testid="cost-tracker"]')).toBeVisible();

    // Step 8: Wait for job completion (with timeout)
    // In real scenario, this could take minutes
    // For E2E test, use short-running test job
    await expect(page.locator('text=COMPLETED')).toBeVisible({ timeout: 60000 });

    // Step 9: Download export
    await page.click('button:has-text("Download JSONL")');

    // Wait for download
    const download = await page.waitForEvent('download', { timeout: 30000 });
    expect(download.suggestedFilename()).toMatch(/\.jsonl$/);

    // Verify download completed
    const path = await download.path();
    expect(path).toBeTruthy();
  });

  test('user can cancel running job', async ({ page }) => {
    // Login first (using existing user from previous test or create new)
    await page.goto('/login');
    // ... login steps ...

    // Navigate to jobs
    await page.goto('/jobs');

    // Find a running job
    const runningJob = page.locator('[data-status="RUNNING"]').first();
    await runningJob.click();

    // Cancel job
    await page.click('button:has-text("Cancel Job")');

    // Confirm cancellation
    await page.click('button:has-text("Confirm")');

    // Verify job cancelled
    await expect(page.locator('text=CANCELLED')).toBeVisible({ timeout: 10000 });
  });

  test('user can view job history', async ({ page }) => {
    // Login
    await page.goto('/login');
    // ... login steps ...

    // Navigate to dashboard
    await page.goto('/dashboard');

    // View all jobs
    await page.click('text=View All Jobs');

    // Verify jobs list
    await expect(page.locator('[data-testid="jobs-table"]')).toBeVisible();

    // Filter by status
    await page.click('select[name="statusFilter"]');
    await page.selectOption('select[name="statusFilter"]', 'COMPLETED');

    // Verify filtered results
    const completedJobs = page.locator('[data-status="COMPLETED"]');
    await expect(completedJobs.first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Error Handling', () => {
  test('shows error when budget is too low', async ({ page }) => {
    await page.goto('/login');
    // ... login steps ...

    await page.goto('/jobs/new');

    // Try to create job with $0.01 budget
    await page.fill('input[name="budgetLimit"]', '0.01');
    await page.click('button:has-text("Create Job")');

    // Should show validation error
    await expect(page.locator('text=Budget too low')).toBeVisible({ timeout: 5000 });
  });

  test('shows error when seed data is invalid', async ({ page }) => {
    await page.goto('/login');
    // ... login steps ...

    await page.goto('/jobs/new');

    // Upload invalid seed data
    await page.setInputFiles('input[type="file"]', {
      name: 'invalid.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{ invalid json'),
    });

    // Should show validation error
    await expect(page.locator('text=Invalid JSON format')).toBeVisible({ timeout: 5000 });
  });
});
