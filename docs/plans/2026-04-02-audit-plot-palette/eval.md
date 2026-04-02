---
type: repo-eval
target: 9
role_level: Senior Developer
date: 2026-04-02
pillar_overrides: {}
---

# Repo Evaluation: plot-palette

## Configuration
- **Role Level:** Senior Developer — production: defensive coding, observability, performance awareness, type rigor
- **Focus Areas:** None — balanced evaluation across all pillars
- **Exclusions:** Standard exclusions (vendor, generated, node_modules, __pycache__)

## Combined Scorecard

| # | Lens | Pillar | Score | Target | Status |
|---|------|--------|-------|--------|--------|
| 1 | Hire | Problem-Solution Fit | 9/10 | 9 | PASS |
| 2 | Hire | Architecture | 9/10 | 9 | PASS |
| 3 | Hire | Code Quality | 8/10 | 9 | NEEDS WORK |
| 4 | Hire | Creativity | 8/10 | 9 | NEEDS WORK |
| 5 | Stress | Pragmatism | 8/10 | 9 | NEEDS WORK |
| 6 | Stress | Defensiveness | 6/10 | 9 | NEEDS WORK |
| 7 | Stress | Performance | 7/10 | 9 | NEEDS WORK |
| 8 | Stress | Type Rigor | 8/10 | 9 | NEEDS WORK |
| 9 | Day 2 | Test Value | 9/10 | 9 | PASS |
| 10 | Day 2 | Reproducibility | 9/10 | 9 | PASS |
| 11 | Day 2 | Git Hygiene | 8/10 | 9 | NEEDS WORK |
| 12 | Day 2 | Onboarding | 9/10 | 9 | PASS |

**Pillars at target (>=9):** 5/12
**Pillars needing work (<9):** 7/12

---

## Hire Evaluation — The Pragmatist

### VERDICT
- **Decision:** STRONG HIRE
- **Overall Grade:** A
- **One-Line:** Solves a genuinely hard distributed systems problem with disciplined architecture, defensive coding, and clear operational insight.

### SCORECARD

| Pillar | Score | Evidence |
|--------|-------|----------|
| Problem-Solution Fit | 9/10 | `backend/shared/models.py:65-144` — Pydantic models with cross-field validation for complex state machines. `backend/lambdas/jobs/create_job.py:88-125` — Proper idempotency checks prevent duplicate jobs. Tech stack (AWS SAM, Bedrock, Step Functions, ECS Fargate Spot) is heavyweight but justified for 10x cost-savings on compute with graceful recovery. |
| Architecture | 9/10 | `backend/shared/aws_clients.py:37-236` — Excellent centralized AWS client factory with connection pooling and differentiated retry configs (120s timeout for Bedrock). `backend/lambdas/` folder shows clear separation: 50+ focused handlers (single responsibility). `backend/ecs_tasks/worker/worker.py:1-100` manages SIGTERM gracefully for Spot interruption. |
| Code Quality | 8/10 | `backend/shared/utils.py:94-132` — Excellent sanitize_error_message() with regex-based redaction. `backend/shared/retry.py:46-147` — Sophisticated circuit breaker with state management. **Concern:** `frontend/src/hooks/useJobStream.ts:68-70` silently ignores parse errors. `backend/lambdas/jobs/create_job.py:14-30` uses `sys.path.insert(0, ...)` anti-pattern. |
| Creativity & Ingenuity | 8/10 | `backend/ecs_tasks/worker/template_engine.py:30-80` — Clever use of Jinja2 SandboxedEnvironment + FunctionLoader for template composition. `backend/shared/retry.py:193-243` — Clean decorator pattern with circuit breaker integration. `frontend/src/hooks/useJobStream.ts:15-101` — Elegant fallback from EventSource to polling with error threshold. Solid engineering, not novel algorithms. |

### HIGHLIGHTS
- **Brilliance:** Robust error handling across the stack — sanitized errors, correlation IDs, idempotency checks, circuit breakers. Spot interruption handling with checkpoint-based recovery is production-grade.
- **Concerns:** Silent error absorption in `frontend/src/hooks/useJobStream.ts:68-70`. `sys.path.insert` anti-pattern in Lambda handlers. Test coverage gaps for worker (integration-only, no unit tests). GSI performance debt in template search.

### REMEDIATION TARGETS

- **Code Quality (current: 8/10 → target: 9/10)**
  - Add structured logging to `frontend/src/hooks/useJobStream.ts` parse error handlers
  - Replace `sys.path.insert(0, ...)` pattern in Lambda handlers with proper package structure
  - Ensure all error absorption is intentional and documented
  - Estimated complexity: MEDIUM

- **Creativity & Ingenuity (current: 8/10 → target: 9/10)**
  - Custom Bedrock token counter (avoid character-based estimation)
  - Adaptive checkpointing based on cost/progress ratios
  - Estimated complexity: HIGH

---

## Stress Evaluation — The Oncall Engineer

### VERDICT
- **Decision:** SENIOR HIRE (with caveats)
- **Seniority Alignment:** Code shows strong operational maturity — good for mid-to-senior IC work, but surface-level issues on production resilience require hardening.
- **One-Line:** Pragmatic, well-intentioned production design that will page you on subtle failure modes and resource exhaustion paths.

### SCORECARD

| Pillar | Score | Evidence |
|--------|-------|----------|
| Pragmatism | 8/10 | `backend/shared/aws_clients.py:20-35` — well-configured client factory with adaptive retries & connection pooling; `backend/shared/models.py:65-92` — Pydantic models enforce invariants strictly. BUT `backend/lambdas/templates/search_templates.py:90` — TODO scan inefficiency; `backend/lambdas/templates/list_templates.py:70` — unindexed public template scans. |
| Defensiveness | 6/10 | `backend/shared/retry.py:149-162` — solid error classification for retryability. BUT `backend/lambdas/jobs/create_job.py:357-359` — bare `except Exception` swallows errors without distinguishing transient vs permanent; `backend/ecs_tasks/worker/worker.py:375-380` — single record failures silently continue; `backend/lambdas/jobs/stream_progress.py:63-66` — KeyError on auth not caught. |
| Performance | 7/10 | `backend/shared/aws_clients.py:21-34` — read/write timeouts sensible; Bedrock client 120s timeout good. BUT `backend/lambdas/templates/search_templates.py:89-107` — unbounded DynamoDB scan capped at 1000 items; `backend/lambdas/templates/list_templates.py:72-92` — post-filter on 100+ items; `backend/ecs_tasks/worker/worker.py:320-321` — O(n) per-record checkpoint cost check in hot loop. |
| Type Rigor | 8/10 | `backend/shared/models.py:1-50` — Pydantic models encode DynamoDB invariants well; `extra="forbid"` prevents schema drift. `backend/shared/constants.py:11-50` — StrEnum discipline. BUT `backend/ecs_tasks/worker/worker.py:278-283` — stringly-typed config with silent float coercion; JSON round-trips lose Decimal type. |

### CRITICAL FAILURE POINTS

1. **Race Condition in Idempotency Check** (`backend/lambdas/jobs/create_job.py:171-176`) — queries for idempotency token without lock; window between check and insert allows duplicate creation under high concurrency. **Severity: HIGH**

2. **Swallowed Errors in Core Lambda Handler** (`backend/lambdas/jobs/create_job.py:357-359`) — bare `except Exception` loses context on auth failures, type errors. Client gets generic 500 for all errors. **Severity: MEDIUM**

3. **Unbounded DynamoDB Scans** (`backend/lambdas/templates/search_templates.py:89-107`, `backend/lambdas/templates/list_templates.py:70-92`) — scans 1000 items in memory; under load 15 requests × 1000 items = 15k RCUs. **Severity: MEDIUM**

4. **ETag Conflict Handling in Checkpoint** (`backend/ecs_tasks/worker/worker.py:516-573`) — retries 3 times on ETag mismatch; if retry fails, silently continues with stale cost tracking. **Severity: MEDIUM-HIGH**

5. **Template Load Failures** (`backend/ecs_tasks/worker/template_engine.py:85-86, 94-95`) — missing templates return HTML comments sent to Bedrock in prompts; jobs complete "successfully" with garbage output. **Severity: MEDIUM**

### HIGHLIGHTS
- **Brilliance:** Circuit Breaker (`backend/shared/retry.py:46-125`), Checkpoint-Based Recovery (`backend/ecs_tasks/worker/worker.py:441-488`), Multi-Mode Orchestration (SFN + standalone), Pydantic-Based Type Enforcement
- **Concerns:** Silent errors in record generation loop, CORS header defaulting to `"null"`, unguarded JWT access, template engine fallback to string comments

### REMEDIATION TARGETS

- **Pragmatism (current: 8/10 → target: 9/10)**
  - Replace DynamoDB scans for public templates with GSI on `(is_public, created_at)`
  - Files: `backend/lambdas/templates/search_templates.py:90`, `list_templates.py:70`, `delete_template.py:41`
  - Estimated complexity: LOW

- **Defensiveness (current: 6/10 → target: 9/10)**
  - Use `ConditionExpression` on `put_item` for idempotency (or TransactWriteItems)
  - Replace bare `except Exception` with typed catches across all Lambda handlers
  - Raise exception on template load failure instead of returning HTML comments
  - Files: `backend/lambdas/jobs/create_job.py:267-274`, all Lambda handlers, `backend/ecs_tasks/worker/template_engine.py:84-95`
  - Estimated complexity: MEDIUM

- **Performance (current: 7/10 → target: 9/10)**
  - Pass pagination token through client-side pagination
  - Move budget check outside hot loop (pre-compute cost-per-record)
  - Files: `backend/lambdas/templates/search_templates.py:89-107`, `backend/ecs_tasks/worker/worker.py:320-323`
  - Estimated complexity: MEDIUM

- **Type Rigor (current: 8/10 → target: 9/10)**
  - Define config as Pydantic BaseModel, parse at Lambda entry point
  - Catch `json.JSONDecodeError` separately with context
  - Files: `backend/shared/models.py:39-55`, `backend/lambdas/quality/score_job.py:136-144`
  - Estimated complexity: MEDIUM

---

## Day 2 Evaluation — The Team Lead

### VERDICT
- **Decision:** TEAM LEAD MATERIAL
- **Collaboration Score:** High
- **One-Line:** Writes code that anticipates future maintenance through proactive documentation, defensive coding patterns, and comprehensive test coverage.

### SCORECARD

| Pillar | Score | Evidence |
|--------|-------|----------|
| Test Value | 9/10 | `tests/unit/test_shared.py` and `tests/integration/test_jobs_api.py` demonstrate behavior-driven testing with extensive fixtures, clear assertions, realistic scenarios. 70+ test files with proper pytest markers (`unit`, `integration`, `worker`, `slow`). |
| Reproducibility | 9/10 | `.github/workflows/ci.yml` implements multi-stage CI: linting → type checking → security → tests with 70% coverage enforcement. Lock files committed. Docker Compose for MiniStack. Pre-commit hooks. 15-minute total setup. |
| Git Hygiene | 8/10 | Commits follow conventional format with scope enumeration. Commitlint enforces 15-character minimum. Some chore commits are verbose but intent always clear. |
| Onboarding | 9/10 | CONTRIBUTING.md provides step-by-step setup (5 steps). `.env.example` documents all variables. `docs/` contains architecture.md, aws-setup.md, troubleshooting.md. PR template guides reviewers. |

### RED FLAGS
- None critical. One minor pattern: env var defaults hardcoded across 30+ Lambda handlers (`os.environ.get("JOBS_TABLE_NAME", "plot-palette-Jobs")`) — missing env var would silently use wrong table.

### HIGHLIGHTS
- **Process Win:** Defensive error handling (`backend/shared/utils.py` sanitize functions), correlation ID tracing via `contextvars`, circuit breaker with state transitions, type-safe DynamoDB serialization, frontend test utilities with custom render wrapper.
- **Maintenance Drag:** 6 test files with placeholder/incomplete test logic. Loose environment variable defaults across Lambda handlers.

### REMEDIATION TARGETS

- **Git Hygiene (current: 8/10 → target: 9/10)**
  - Enforce that each commit has one reason-to-revert
  - Add scope-based grouping guidelines in CONTRIBUTING.md
  - Estimated complexity: LOW

---

## Consolidated Remediation Targets

Merged and deduplicated across all 3 evaluators, prioritized by lowest score first:

### Priority 1: Defensiveness (6/10 → 9/10) — Stress
- Idempotency race condition: use `ConditionExpression` or `TransactWriteItems`
- Error typing pass: replace bare `except Exception` with typed catches in all Lambda handlers
- Template engine: raise exception on missing templates instead of returning HTML comments
- Checkpoint ETag: handle retry exhaustion explicitly
- **Files:** `create_job.py`, all Lambda handlers, `template_engine.py`, `worker.py`
- **Complexity:** MEDIUM

### Priority 2: Performance (7/10 → 9/10) — Stress
- Add GSI for public template queries (replaces scan)
- Client-side pagination tokens
- Move budget check outside hot loop
- **Files:** `search_templates.py`, `list_templates.py`, `delete_template.py`, `worker.py`
- **Complexity:** MEDIUM (GSI is LOW, pagination is MEDIUM)

### Priority 3: Code Quality (8/10 → 9/10) — Hire
- Structured logging for silent error absorption in `useJobStream.ts`
- Remove `sys.path.insert` anti-pattern from Lambda handlers
- Document all intentional error suppression
- **Files:** `useJobStream.ts`, Lambda handler imports
- **Complexity:** MEDIUM

### Priority 4: Pragmatism (8/10 → 9/10) — Stress
- Overlaps with Performance GSI work (consolidated above)
- **Complexity:** LOW (covered by Priority 2)

### Priority 5: Type Rigor (8/10 → 9/10) — Stress
- Config type safety: Pydantic BaseModel for job config
- JSON deserialization error recovery with context
- **Files:** `models.py`, `score_job.py`
- **Complexity:** MEDIUM

### Priority 6: Git Hygiene (8/10 → 9/10) — Day 2
- Documentation-only: add commit scope guidelines to CONTRIBUTING.md
- **Complexity:** LOW

### Priority 7: Creativity (8/10 → 9/10) — Hire
- Custom token counter, adaptive checkpointing
- **Complexity:** HIGH (domain expertise required)
