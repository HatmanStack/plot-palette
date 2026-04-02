# Unified Audit Remediation Plan

## Overview

This plan remediates findings from three concurrent audits of the plot-palette codebase:
a health audit (49 findings across CRITICAL/HIGH/MEDIUM/LOW), a 12-pillar evaluation
(7 pillars below the 9/10 target), and a documentation audit (3 drift findings, 1 gap).

The work is sequenced in four stages: (1) HYGIENIST phases remove dead code, unused
dependencies, and simplify; (2) IMPLEMENTER phases fix architectural gaps, error handling,
and performance; (3) FORTIFIER phases add guardrails for type safety and defensive coding;
(4) DOC-ENGINEER phases fix documentation drift and close gaps.

## Prerequisites

- Node.js 18+ and npm installed
- Python 3.13 with `uv` package manager
- Docker (for E2E tests)
- AWS CLI configured (for running backend tests with moto mocks)
- Repository cloned and dependencies installed per CLAUDE.md setup instructions

## Phase Summary

| Phase | Tag | Goal | Est. Tokens |
|-------|-----|------|-------------|
| 0 | -- | Foundation: ADRs, testing strategy, conventions | ~5k |
| 1 | HYGIENIST | Dead code removal, unused deps, simplify | ~12k |
| 2 | IMPLEMENTER | Critical error handling and operational fixes | ~25k |
| 3 | IMPLEMENTER | Performance and architecture improvements | ~15k |
| 4 | FORTIFIER | Type safety, defensive coding, guardrails | ~15k |
| 5 | DOC-ENGINEER | Documentation drift fixes and gap closure | ~8k |

## Findings Not Addressed

The following findings were evaluated and intentionally excluded:

- **Health audit HIGH-2** (Bedrock 120s timeout): The 120s read timeout is a
  reasonable value for LLM inference. Reducing it risks premature timeouts on
  large generations. No change needed.
- **Health audit HIGH-6** (Batch partial creation rollback): Fixing this requires
  DynamoDB TransactWriteItems with a max of 100 items, which conflicts with
  unbounded batch sizes. This is a feature-level design change, not a remediation fix.
- **Health audit LOW-4** (Worker distributed job claiming race): The current
  conditional write pattern is standard for DynamoDB. The rare double-claim is
  handled by idempotent processing. No change needed.
- **Eval Creativity (8/10)**: Custom token counter and adaptive checkpointing are
  feature work, not remediation. Excluded per scope.

## Navigation

- [Phase-0.md](Phase-0.md) -- Foundation (applies to all phases)
- [Phase-1.md](Phase-1.md) -- [HYGIENIST] Cleanup and simplification
- [Phase-2.md](Phase-2.md) -- [IMPLEMENTER] Critical error handling and operational fixes
- [Phase-3.md](Phase-3.md) -- [IMPLEMENTER] Performance and architecture improvements
- [Phase-4.md](Phase-4.md) -- [FORTIFIER] Type safety and defensive coding
- [Phase-5.md](Phase-5.md) -- [DOC-ENGINEER] Documentation fixes
- [feedback.md](feedback.md) -- Review feedback log
