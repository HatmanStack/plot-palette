# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Conventional Commits](https://www.conventionalcommits.org/).

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
