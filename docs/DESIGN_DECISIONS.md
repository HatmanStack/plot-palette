# Design Decisions & Implementation Notes

This document captures design decisions made during implementation that differ from or clarify the original plan.

## Phase 1: Core Infrastructure

### S3 Folder Structure (Task 2)

**Decision:** Do not create placeholder `.keep` files for S3 folder structure in CloudFormation.

**Rationale:**
- `AWS::S3::Object` is not a valid CloudFormation resource type
- Alternative approaches (Lambda custom resource, AWS CLI in UserData) add unnecessary complexity
- S3 doesn't have true folders - they're just key prefixes
- Folders will be created automatically when first object is uploaded to that prefix
- Lifecycle rules reference prefixes (`jobs/`, `seed-data/`, etc.) which work regardless of placeholder files

**Impact:**
- No functional difference - folders appear in S3 console when objects are added
- Cleaner CloudFormation template without custom resources
- Simpler deployment (no Lambda dependency for folder creation)

**References:**
- Plan: Phase-1.md lines 210-215
- Implementation: `infrastructure/cloudformation/storage-stack.yaml`

### Backend Dependencies Installation

**Decision:** Added explicit dependency installation instructions in README and backend/README.md.

**Rationale:**
- Unit tests require dependencies to be installed
- Imports fail without `pydantic`, `boto3`, etc.
- Not all users will deploy - some may want local development only
- Clear setup instructions improve developer experience

**Implementation:**
- Created `backend/README.md` with setup guide
- Updated main `README.md` with optional step for local development
- Included verification command to test imports work

**References:**
- Review feedback: Phase-1.md lines 1140-1143
- Implementation: `README.md` lines 122-135, `backend/README.md`

---

*This document will be updated as additional design decisions are made in subsequent phases.*
