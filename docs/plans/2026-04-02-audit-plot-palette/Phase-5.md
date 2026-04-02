# Phase 5: [DOC-ENGINEER] Documentation Fixes

## Phase Goal

Fix all documentation drift, close documentation gaps, and fix the deploy script
to output correct environment variable names. These are the findings from the
documentation audit.

**Success criteria:** All 3 drift findings resolved, 1 gap finding resolved, deploy
script corrected.

**Estimated tokens:** ~8,000

## Prerequisites

- Phases 1-4 complete (code changes that docs reference are stable)
- All tests passing

## Tasks

### Task 1: Fix Cognito environment variable names in docs

**Goal:** Two documentation files reference wrong environment variable names for
Cognito configuration. The docs say `VITE_USER_POOL_ID` and `VITE_USER_POOL_CLIENT_ID`
but the code uses `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`.

**Source:** Doc audit DRIFT-1

**Files to Modify:**

- `docs/aws-setup.md` -- Fix variable names in the .env table (around line 49-50)
- `docs/troubleshooting.md` -- Fix variable name reference (around line 13)

**Prerequisites:**

- Read `docs/aws-setup.md` lines 46-52 to see the current table
- Read `docs/troubleshooting.md` line 13 to see the reference
- Verify against `.env.example` lines 18-19 and `frontend/src/services/auth.ts` lines 9-10

**Implementation Steps:**

- In `docs/aws-setup.md`, update the `.env` variable table:
  - Change `VITE_USER_POOL_ID` to `VITE_COGNITO_USER_POOL_ID`
  - Change `VITE_USER_POOL_CLIENT_ID` to `VITE_COGNITO_CLIENT_ID`
- In `docs/troubleshooting.md`, update any references to use the correct variable names
- Verify the corrected names match `.env.example` and `frontend/src/services/auth.ts`

**Verification Checklist:**

- [x] `docs/aws-setup.md` uses `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`
- [x] `docs/troubleshooting.md` uses correct variable names
- [x] Variable names match `.env.example` exactly
- [x] Variable names match `frontend/src/services/auth.ts` exactly

**Testing Instructions:**

- No automated tests -- manual verification against `.env.example` and source code

**Commit Message Template:**

```text
docs: fix Cognito environment variable names in setup guides

- Addresses doc-audit DRIFT-1
- Aligns docs with .env.example and frontend/src/services/auth.ts
```

---

### Task 2: Remove VITE_REGION from docs

**Goal:** The docs tell users to set `VITE_REGION` but the frontend code does not
use this variable anywhere. Remove the reference to avoid confusion.

**Source:** Doc audit DRIFT-2

**Files to Modify:**

- `docs/aws-setup.md` -- Remove VITE_REGION row from the table (around line 51)

**Implementation Steps:**

- Remove the row `| VITE_REGION | Your chosen region |` from the .env table
- Search the rest of the docs for any other references to `VITE_REGION` and remove them

**Verification Checklist:**

- [x] `VITE_REGION` is not mentioned anywhere in docs
- [x] Remaining table entries are all valid and used by the code

**Testing Instructions:**

- No automated tests -- search docs for `VITE_REGION` to verify removal

**Commit Message Template:**

```text
docs: remove unused VITE_REGION from setup guide

- Addresses doc-audit DRIFT-2
- Frontend code does not read VITE_REGION
```

---

### Task 3: Fix deploy script variable names

**Goal:** The deploy script echoes wrong frontend environment variable names.
It outputs `VITE_USER_POOL_ID` and `VITE_CLIENT_ID` but the frontend expects
`VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`.

**Source:** Doc audit DRIFT-3

**Files to Modify:**

- `scripts/deploy.sh` -- Fix echoed variable names (around line 258-262)

**Prerequisites:**

- Read `scripts/deploy.sh` lines 255-270 to see the current output

**Implementation Steps:**

- Change the echo output to use the correct variable names:
  - `VITE_USER_POOL_ID` becomes `VITE_COGNITO_USER_POOL_ID`
  - `VITE_CLIENT_ID` becomes `VITE_COGNITO_CLIENT_ID`
  - `VITE_API_URL` -- verify this matches what the frontend expects
    (`VITE_API_ENDPOINT` per `.env.example`). If different, fix this too.
  - `VITE_AWS_REGION` -- the frontend does not use this (per DRIFT-2). Remove
    this line.
- Also fix the Expo section if it exists (lines 263-268) -- though Expo variables
  are outside the scope of this project, keeping them consistent is good practice

**Verification Checklist:**

- [ ] Deploy script echoes `VITE_COGNITO_USER_POOL_ID` (not `VITE_USER_POOL_ID`)
- [ ] Deploy script echoes `VITE_COGNITO_CLIENT_ID` (not `VITE_CLIENT_ID`)
- [ ] Deploy script echoes `VITE_API_ENDPOINT` (not `VITE_API_URL`, if applicable)
- [ ] No reference to `VITE_AWS_REGION` in the frontend section
- [ ] Variable names match `.env.example`

**Testing Instructions:**

- No automated tests -- manual review of deploy script output

**Commit Message Template:**

```text
fix(docs): correct frontend env var names in deploy script

- Addresses doc-audit DRIFT-3
- Aligns deploy.sh output with .env.example and frontend code
```

---

### Task 4: Document BATCHES_TABLE_NAME environment variable

**Goal:** The `BATCHES_TABLE_NAME` environment variable is used by 4 Lambda handlers
but is not documented in `.env.example` or `docs/architecture.md`.

**Source:** Doc audit GAP-1

**Files to Modify:**

- `.env.example` -- Add BATCHES_TABLE_NAME
- `docs/architecture.md` -- Add Batches table to the database schema section

**Prerequisites:**

- Read `.env.example` to find where to add the new variable (after other table names)
- Read `docs/architecture.md` lines 48-54 to find the database schema table

**Implementation Steps:**

- In `.env.example`, add after `CHECKPOINT_METADATA_TABLE_NAME`:
  `BATCHES_TABLE_NAME=plot-palette-Batches-dev`
- In `docs/architecture.md`, add the Batches table to the database schema list with
  a brief description of what it stores (batch job metadata)

**Verification Checklist:**

- [ ] `BATCHES_TABLE_NAME` is in `.env.example`
- [ ] Batches table is documented in `docs/architecture.md`
- [ ] Default value follows the naming pattern of other tables

**Testing Instructions:**

- No automated tests -- verify presence in files

**Commit Message Template:**

```text
docs: document BATCHES_TABLE_NAME environment variable

- Addresses doc-audit GAP-1
- Adds to .env.example and architecture.md
```

---

### Task 5: Add commit scope guidelines to CONTRIBUTING.md

**Goal:** The eval identified that commit scope guidelines are not documented.
Add a brief section to CONTRIBUTING.md with scope conventions.

**Source:** Eval git hygiene

**Files to Modify:**

- `CONTRIBUTING.md` -- Add commit scope guidelines

**Prerequisites:**

- Read `CONTRIBUTING.md` to find the existing commit message section

**Implementation Steps:**

- Find the section about commit messages in CONTRIBUTING.md
- Add a subsection listing valid scopes and when to use each:
  - `lambda` -- Lambda handler changes
  - `worker` -- ECS worker changes
  - `shared` -- Shared module changes (models, utils, retry, etc.)
  - `frontend` -- React/TypeScript frontend changes
  - `docker` -- Dockerfile and container changes
  - `docs` -- Documentation changes
  - `ci` -- CI/CD pipeline changes
  - `deps` -- Dependency updates
- Include guidance: "Each commit should have one reason to revert. If a commit
  touches multiple scopes, use the most impactful scope."

**Verification Checklist:**

- [ ] Scope list added to CONTRIBUTING.md
- [ ] Guidance on choosing scopes included
- [ ] Follows existing document formatting conventions

**Testing Instructions:**

- No automated tests -- review for completeness

**Commit Message Template:**

```text
docs: add commit scope guidelines to CONTRIBUTING.md

- Addresses eval git hygiene target
- Lists valid scopes with usage guidance
```

## Phase Verification

- All documentation changes verified against source code
- No broken links in modified docs
- `.env.example` has all environment variables used by the code
- Deploy script output matches `.env.example` variable names
- CONTRIBUTING.md has clear commit scope guidance
- Run markdownlint on modified files to verify formatting
