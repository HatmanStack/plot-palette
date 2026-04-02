---
type: doc-health
date: 2026-04-02
prevention_scope: Markdown linting (markdownlint) + link checking (lychee)
language_stack: Both (JS/TS + Python)
---

# Documentation Audit: plot-palette

## Configuration
- **Prevention Scope:** Markdown linting (markdownlint) + link checking (lychee)
- **Language Stack:** Both (JS/TS + Python)
- **Constraints:** None — all docs, no exclusions

## Summary
- Docs scanned: 9 files (README.md, architecture.md, aws-setup.md, troubleshooting.md, openapi.yaml, CONTRIBUTING.md, CHANGELOG.md, plus plan docs)
- Code modules scanned: 35+ Lambda handlers, 1 ECS worker, 50+ frontend React modules
- Findings: 3 drift, 1 gap, 0 stale, 0 broken links

## Findings

### DRIFT (doc exists, doesn't match code)

1. **`docs/aws-setup.md:49-50` and `docs/troubleshooting.md:13`** → `frontend/src/services/auth.ts:9-10`
   - Doc says: `.env` variables are named `VITE_USER_POOL_ID` and `VITE_USER_POOL_CLIENT_ID`
   - Code uses: `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`
   - `.env.example:18-19` shows `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`
   - `frontend/src/services/auth.ts:9-10` reads `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`
   - `frontend/src/test/setup.ts:15-16` mocks `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`
   - **Impact:** Following the AWS setup guide will create `.env` variables with wrong names, causing auth failures at runtime.

2. **`docs/aws-setup.md:51`** → Code doesn't use this variable
   - Doc says: Need to set `VITE_REGION` from SAM output "Your chosen region"
   - Code reality: Frontend code does not read `VITE_REGION` anywhere
   - **Impact:** Users will set unused environment variable, creating confusion about deployment configuration.

3. **`scripts/deploy.sh:260`** → docs/aws-setup.md
   - Doc says: Variable name is `VITE_USER_POOL_ID`
   - Deploy script echoes: `VITE_USER_POOL_ID=$COGNITO_USER_POOL_ID`
   - Reality: Script assigns correct value but under wrong variable name
   - Note: Both docs and script are wrong; should use `VITE_COGNITO_USER_POOL_ID`

### GAPS (code exists, no doc)

1. **`BATCHES_TABLE_NAME` environment variable** → Not documented
   - Code reads: `backend/lambdas/jobs/create_batch.py:35`, `delete_batch.py:28`, `get_batch.py:29`, `list_batches.py:20` all call `os.environ.get("BATCHES_TABLE_NAME")`
   - Missing from: `.env.example` does not list `BATCHES_TABLE_NAME` (while other table names are listed on lines 7-11)
   - Missing from: `docs/architecture.md` database schema table (line 48-54) lists 5 tables but omits Batches table
   - **Impact:** Deploying without setting `BATCHES_TABLE_NAME` will cause batch operations to fail or use wrong table.

### STALE (doc exists, code doesn't)

None detected. All referenced files, endpoints, and features verified to exist.

### BROKEN LINKS

None detected. All internal references verified:
- `[Troubleshooting](docs/troubleshooting.md)` → exists
- `[Architecture Overview](docs/architecture.md)` → exists
- `[AWS Setup Guide](docs/aws-setup.md)` → exists
- `[API Reference](docs/openapi.yaml)` → exists
- `[Contributing](CONTRIBUTING.md)` → exists
- Banner image `banner.png` → exists at repo root

### STALE CODE EXAMPLES

None detected. All code snippets in documentation match current implementation.

### CONFIG DRIFT

**Frontend Variables (.env.example vs frontend code):**
- `VITE_COGNITO_USER_POOL_ID` → defined in `.env.example:18`, used in `frontend/src/services/auth.ts:9` ✓
- `VITE_COGNITO_CLIENT_ID` → defined in `.env.example:19`, used in `frontend/src/services/auth.ts:10` ✓
- `VITE_API_ENDPOINT` → defined in `.env.example:20`, used in `frontend/src/services/api.ts:63` ✓
- `VITE_REGION` → NOT in `.env.example`, NOT used in frontend code (see DRIFT #2)

**Backend Variables (.env.example vs backend code):**
- `JOBS_TABLE_NAME` → defined in `.env.example:7`, used in 10+ Lambda handlers ✓
- `QUEUE_TABLE_NAME` → defined in `.env.example:8`, used in 2 Lambda handlers ✓
- `TEMPLATES_TABLE_NAME` → defined in `.env.example:9`, used in 10+ Lambda handlers ✓
- `COST_TRACKING_TABLE_NAME` → defined in `.env.example:10`, used in 4 Lambda handlers ✓
- `CHECKPOINT_METADATA_TABLE_NAME` → defined in `.env.example:11`, used in worker ✓
- `BUCKET_NAME` → defined in `.env.example:12`, used in 15+ Lambda handlers and worker ✓
- `BATCHES_TABLE_NAME` → NOT in `.env.example`, IS used in 4 Lambda handlers (see GAP #1)

**Pricing values:** All Bedrock model pricing in `docs/aws-setup.md:79-80` matches `backend/shared/constants.py:54-74` exactly.

### STRUCTURE ISSUES

1. **Plan documents not referenced from main docs**
   - `docs/plans/v1.2/` contains implementation guides but are isolated
   - Not indexed in main documentation hierarchy
   - Assessment: These appear to be internal planning documents — may be intentional

2. **OpenAPI specification not validated**
   - `docs/openapi.yaml` exists and is referenced in README
   - Content verified to be valid OpenAPI 3.0.3 schema
   - No validation tools mentioned in pre-commit hooks or CI
