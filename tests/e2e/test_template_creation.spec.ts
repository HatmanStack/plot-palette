/**
 * E2E Test: Template Creation and Testing
 *
 * Tests template CRUD operations and template testing functionality.
 *
 * NOTE: Phase 8 is code writing only. These tests will run against
 * deployed infrastructure in Phase 9.
 */

import { test, expect } from '@playwright/test';

const testTemplate = {
  name: 'Test Creative Writing Template',
  description: 'Template for generating creative writing samples',
  prompt: `Generate a creative story based on:

Author: {{ author.name }}
Genre: {{ author.genre }}
Theme: {{ poem.text | random_sentence }}

Write a compelling narrative in the style of {{ author.biography | writing_style }}.`,
};

test.describe('Template Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');

    // Navigate to templates page
    await page.goto('/templates');
  });

  test('create new template with basic prompt', async ({ page }) => {
    // Click new template button
    await page.click('button:has-text("New Template")');

    // Fill template form
    await page.fill('input[name="name"]', testTemplate.name);
    await page.fill('textarea[name="description"]', testTemplate.description);
    await page.fill('textarea[name="prompt"]', testTemplate.prompt);

    // Save template
    await page.click('button:has-text("Save")');

    // Verify template created
    await expect(page.locator('text=Template created successfully')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${testTemplate.name}`)).toBeVisible();
  });

  test('create multi-step template', async ({ page }) => {
    await page.click('button:has-text("New Template")');

    // Fill basic info
    await page.fill('input[name="name"]', 'Multi-Step Template');

    // Add first step
    await page.fill('textarea[name="steps[0].prompt"]', 'Generate question about {{ topic }}');
    await page.selectOption('select[name="steps[0].model"]', 'meta.llama3-1-8b-instruct-v1:0');

    // Add second step
    await page.click('button:has-text("Add Step")');
    await page.fill('textarea[name="steps[1].prompt"]', 'Answer: {{ steps.step1.output }}');
    await page.selectOption('select[name="steps[1].model"]', 'anthropic.claude-3-5-sonnet-20241022-v2:0');

    // Save
    await page.click('button:has-text("Save")');

    // Verify
    await expect(page.locator('text=Template created successfully')).toBeVisible({ timeout: 10000 });
  });

  test('template with custom filters', async ({ page }) => {
    await page.click('button:has-text("New Template")');

    const filterTemplate = `Extract key themes: {{ text | extract_keywords }}
Random sentence: {{ text | random_sentence }}
Truncated: {{ text | truncate_tokens(100) }}`;

    await page.fill('input[name="name"]', 'Filter Test Template');
    await page.fill('textarea[name="prompt"]', filterTemplate);

    await page.click('button:has-text("Save")');

    await expect(page.locator('text=Template created successfully')).toBeVisible({ timeout: 10000 });
  });

  test('template with conditionals', async ({ page }) => {
    await page.click('button:has-text("New Template")');

    const conditionalTemplate = `{% if author.genre == "poetry" %}
Generate a poem about {{ author.name }}
{% else %}
Generate a story about {{ author.name }}
{% endif %}`;

    await page.fill('input[name="name"]', 'Conditional Template');
    await page.fill('textarea[name="prompt"]', conditionalTemplate);

    await page.click('button:has-text("Save")');

    await expect(page.locator('text=Template created successfully')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Template Testing', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.goto('/templates');
  });

  test('test template with sample data', async ({ page }) => {
    // Find first template
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    // Click test button
    await page.click('button:has-text("Test Template")');

    // Fill test data
    const testData = {
      author: {
        name: 'Jane Doe',
        biography: 'A celebrated poet',
        genre: 'poetry',
      },
      poem: {
        text: 'Roses are red. Violets are blue.',
      },
    };

    await page.fill('textarea[name="testData"]', JSON.stringify(testData, null, 2));

    // Run test
    await page.click('button:has-text("Run Test")');

    // Verify preview
    await expect(page.locator('[data-testid="template-preview"]')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Jane Doe')).toBeVisible();
  });

  test('test template shows validation errors', async ({ page }) => {
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    await page.click('button:has-text("Test Template")');

    // Invalid JSON
    await page.fill('textarea[name="testData"]', '{ invalid json }');
    await page.click('button:has-text("Run Test")');

    // Should show error
    await expect(page.locator('text=Invalid JSON')).toBeVisible({ timeout: 5000 });
  });

  test('test template with missing required fields', async ({ page }) => {
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    await page.click('button:has-text("Test Template")');

    // Data missing required fields
    const incompleteData = {
      author: {
        name: 'Jane Doe',
        // Missing biography and genre
      },
    };

    await page.fill('textarea[name="testData"]', JSON.stringify(incompleteData, null, 2));
    await page.click('button:has-text("Run Test")');

    // Should show validation error
    await expect(page.locator('text=Missing required field')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Template Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.goto('/templates');
  });

  test('edit existing template', async ({ page }) => {
    // Find and click first template
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    // Click edit button
    await page.click('button:has-text("Edit")');

    // Modify template
    await page.fill('input[name="name"]', 'Updated Template Name');
    await page.click('button:has-text("Save")');

    // Verify update
    await expect(page.locator('text=Template updated successfully')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Updated Template Name')).toBeVisible();
  });

  test('duplicate template', async ({ page }) => {
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    // Click duplicate button
    await page.click('button:has-text("Duplicate")');

    // Verify copy created
    await expect(page.locator('text=Template duplicated')).toBeVisible({ timeout: 10000 });
  });

  test('delete template', async ({ page }) => {
    const firstTemplate = page.locator('[data-testid="template-card"]').first();
    await firstTemplate.click();

    // Click delete button
    await page.click('button:has-text("Delete")');

    // Confirm deletion
    await page.click('button:has-text("Confirm Delete")');

    // Verify deleted
    await expect(page.locator('text=Template deleted')).toBeVisible({ timeout: 10000 });
  });

  test('search templates', async ({ page }) => {
    // Search for template
    await page.fill('input[placeholder="Search templates..."]', 'creative');

    // Verify filtered results
    const results = page.locator('[data-testid="template-card"]');
    await expect(results.first()).toBeVisible({ timeout: 5000 });
  });

  test('filter templates by type', async ({ page }) => {
    // Filter by public templates
    await page.click('button:has-text("Public")');

    // Verify filtered results
    const publicTemplates = page.locator('[data-testid="template-card"][data-public="true"]');
    await expect(publicTemplates.first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Template Validation', () => {
  test('show error for invalid Jinja2 syntax', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.goto('/templates');

    await page.click('button:has-text("New Template")');

    // Invalid Jinja2
    await page.fill('input[name="name"]', 'Invalid Template');
    await page.fill('textarea[name="prompt"]', 'Bad syntax {{ unclosed');

    await page.click('button:has-text("Save")');

    // Should show validation error
    await expect(page.locator('text=Invalid template syntax')).toBeVisible({ timeout: 5000 });
  });

  test('show warning for unknown variables', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TEST_USER_EMAIL || 'test@example.com');
    await page.fill('input[name="password"]', process.env.TEST_USER_PASSWORD || 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.goto('/templates');

    await page.click('button:has-text("New Template")');

    await page.fill('input[name="name"]', 'Template with Unknown Vars');
    await page.fill('textarea[name="prompt"]', 'Use {{ unknown.variable }}');

    // Should show warning
    await expect(page.locator('text=Unknown variable')).toBeVisible({ timeout: 5000 });
  });
});
