# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Conventional Commits](https://www.conventionalcommits.org/).

## [1.2.0] - 2026-02-23

### Added
- Partial result download for in-progress jobs
- Template version history with diff view (Monaco DiffEditor)
- Template version selection in job creation wizard
- Cost analytics dashboard with daily/model breakdowns
- Template marketplace with browse, search, and fork
- Notification preferences (email via SES, webhook POST)
- SSE-based real-time job progress streaming
- Batch job creation with parameter sweep support
- Seed data generation from template schemas
- Automated quality scoring for completed jobs (Bedrock LLM evaluation)
- Manual quality scoring trigger endpoint
- Quality score report in job and batch detail views
- Integration tests for all new endpoints

### Changed
- Webhook URL validator uses static IP-literal checks instead of blocking DNS lookup
- Notification preferences use optimistic locking (DynamoDB ConditionExpression)
- `send_notification` webhook dispatch validates resolved IPs against SSRF blocklist
- Template fork/delete mutations use narrowed query invalidation
- Cost analytics uses `MODEL_PRICING` from constants instead of duplicate dict
- `search_templates` scan capped with `Limit: 100` per page
- `send_notification` responses standardized via `_sfn_response` helper

### Fixed
- SSRF vulnerability in webhook dispatch (DNS rebinding via `urlopen` without IP validation)
- Race condition in notification preferences update (concurrent writes)
- Unsafe `(error as Error).message` cast in BatchDetail
- `JSON.stringify` React key causing unnecessary re-renders in Settings
- Stale result displayed on JSON parse error in SeedDataGenerator
- Missing ESC key handler on TemplatePreview modal
- Missing Space key support in VersionList keyboard navigation
- Missing `aria-label` on QualityScoreBar progress bar
- Silent `pass` on job fetch failure in `get_batch` (now returns `jobs_load_error` flag)
- Unvalidated pagination cursor structure in `list_batches`
- Missing `sample_size` range validation in `trigger_scoring`
- Orphaned SCORING records on unexpected errors in `score_job`
- Bandit B310 finding on `urlopen` (scheme validated upstream)
- Hanging `test_delete_batch_cancels_running` (unmocked S3 paginator)

## [1.1.0] - 2026-02-22

### Added
- Architecture overview, AWS setup guide, and troubleshooting docs
- Detailed setup section in README linking to all docs
- Commitlint with scope enum and subject-min-length enforcement
- Structured PR template with Why/What/Scope & Risk sections
- Real checkpoint integration tests (ETag conflict retry, SIGTERM handler, max retries)
- Zod validation rejection and network error propagation tests for API service
- Toast dismiss button aria-label for accessibility
- Toast timer cleanup on dismiss and unmount

### Changed
- Replaced brittle Tailwind CSS assertions with behavioral StatusBadge tests
- Replaced conventional-pre-commit with commitlint-pre-commit-hook (v9.24.0)
- CORS response headers now use `.copy()` to prevent shared dict mutation
- AWS setup docs use correct SAM AllowedValues (dev/staging/prod)

### Removed
- 438 lines of checkpoint unit test theater (no real code exercised)

### Fixed
- CORS_HEADERS shared mutable dict could be modified by callers
- Toast auto-dismiss timers leaked on early dismissal or unmount
