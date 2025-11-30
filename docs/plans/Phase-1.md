# Phase 1: Frontend Tests

## Phase Goal

Add comprehensive unit tests for React hooks, contexts, and key UI components. Tests will focus on user-facing behavior and serve as living documentation of expected functionality.

**Success Criteria:**
- All hooks have unit tests covering happy path and error cases
- AuthContext/AuthProvider tested for all auth states
- Key UI components (JobCard, StatusBadge, PrivateRoute) fully tested
- Form components tested for validation and submission flows
- `npm test` passes with no failures

**Estimated Tokens:** ~35,000

## Prerequisites

- Phase 0 complete (test utilities and mock factories available)
- `frontend/src/test/test-utils.tsx` exists with custom render
- `frontend/src/test/mocks/auth.ts` and `api.ts` exist

---

## Tasks

### Task 1: Test useAuth Hook

**Goal:** Test the useAuth hook that provides authentication context access with proper error handling.

**Files to Create:**
- `frontend/src/hooks/useAuth.test.ts`

**Prerequisites:**
- Phase 0 Task 1 complete

**Implementation Steps:**

1. **Test hook throws outside provider**
   - Render hook without AuthProvider wrapper
   - Verify it throws "useAuth must be used within AuthProvider" error
   - Use `renderHook` from `@testing-library/react`

2. **Test hook returns context inside provider**
   - Wrap hook in AuthProvider
   - Verify all context properties are accessible:
     - `isAuthenticated`
     - `idToken`
     - `login`
     - `signup`
     - `logout`
     - `loading`

3. **Test type safety**
   - Verify return type matches `AuthContextType`

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/hooks/useAuth.test.ts`
- [ ] Error case tested (hook outside provider)
- [ ] Happy path tested (hook inside provider)
- [ ] Tests pass: `npm test -- useAuth`

**Testing Instructions:**
```bash
cd frontend && npm test -- useAuth
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add useAuth hook tests

- Test error when used outside AuthProvider
- Test context values accessible inside provider
```

---

### Task 2: Test useJobs Hook

**Goal:** Test the useJobs hook that fetches and caches job data using React Query.

**Files to Create:**
- `frontend/src/hooks/useJobs.test.ts`

**Prerequisites:**
- Phase 0 Task 1 complete (QueryClient wrapper)

**Implementation Steps:**

1. **Mock the API module**
   - Mock `../services/api` module
   - Configure `fetchJobs` to return test data

2. **Test successful data fetching**
   - Render hook with QueryClient wrapper
   - Wait for query to resolve
   - Verify `data` contains expected jobs array
   - Verify `isLoading` transitions from true to false
   - Verify `isError` is false

3. **Test error handling**
   - Configure mock to reject with error
   - Verify `isError` is true
   - Verify `error` contains error information

4. **Test refetch interval**
   - Verify hook is configured with 10-second refetch interval
   - This can be tested by checking the queryKey configuration

5. **Test empty state**
   - Configure mock to return empty array
   - Verify `data` is empty array, not undefined

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/hooks/useJobs.test.ts`
- [ ] Success case with data tested
- [ ] Error case tested
- [ ] Empty state tested
- [ ] Tests pass: `npm test -- useJobs`

**Testing Instructions:**
```bash
cd frontend && npm test -- useJobs
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add useJobs hook tests

- Test successful job fetching
- Test error handling
- Test empty state
```

---

### Task 3: Test useJobPolling Hook

**Goal:** Test the useJobPolling hook that polls job details with conditional refetch intervals.

**Files to Create:**
- `frontend/src/hooks/useJobPolling.test.ts`

**Prerequisites:**
- Task 2 complete (similar patterns)

**Implementation Steps:**

1. **Mock the API module**
   - Mock `fetchJobDetails` to return configurable job data

2. **Test polling for RUNNING job**
   - Return job with status `RUNNING`
   - Verify refetch interval is active (5 seconds)
   - Use `vi.useFakeTimers()` to control time

3. **Test polling for QUEUED job**
   - Return job with status `QUEUED`
   - Verify refetch interval is active (5 seconds)

4. **Test polling stops for COMPLETED job**
   - Return job with status `COMPLETED`
   - Verify refetch interval is disabled (returns false)

5. **Test polling stops for FAILED job**
   - Return job with status `FAILED`
   - Verify refetch interval is disabled

6. **Test polling stops for CANCELLED job**
   - Return job with status `CANCELLED`
   - Verify refetch interval is disabled

7. **Test with correct jobId**
   - Verify `fetchJobDetails` is called with provided jobId
   - Verify queryKey includes jobId

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/hooks/useJobPolling.test.ts`
- [ ] Polling active for RUNNING/QUEUED tested
- [ ] Polling disabled for terminal states tested
- [ ] JobId passed correctly tested
- [ ] Tests pass: `npm test -- useJobPolling`

**Testing Instructions:**
```bash
cd frontend && npm test -- useJobPolling
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add useJobPolling hook tests

- Test conditional polling based on job status
- Test polling stops for terminal states
- Test jobId parameter handling
```

---

### Task 4: Test AuthContext and AuthProvider

**Goal:** Test the AuthProvider component and its authentication state management.

**Files to Create:**
- `frontend/src/contexts/AuthContext.test.tsx`

**Prerequisites:**
- Phase 0 Task 1 complete (auth mock factory)

**Implementation Steps:**

1. **Mock auth service**
   - Mock `../services/auth` module entirely
   - Configure `getIdToken`, `signIn`, `signUp`, `signOut`

2. **Test initial loading state**
   - Render AuthProvider
   - Verify `loading` is initially true
   - Verify `isAuthenticated` is false initially

3. **Test auto-authentication check on mount**
   - Configure `getIdToken` to return a token
   - Render AuthProvider
   - Wait for loading to complete
   - Verify `isAuthenticated` becomes true
   - Verify `idToken` is set

4. **Test failed auto-authentication**
   - Configure `getIdToken` to throw error
   - Render AuthProvider
   - Wait for loading to complete
   - Verify `isAuthenticated` remains false
   - Verify no error is thrown to UI

5. **Test login function**
   - Configure `signIn` to return token
   - Call `login(email, password)` from context
   - Verify `signIn` called with correct args
   - Verify `isAuthenticated` becomes true
   - Verify `idToken` is set

6. **Test login failure**
   - Configure `signIn` to reject
   - Call `login(email, password)`
   - Verify error is propagated (for UI handling)

7. **Test signup function**
   - Configure `signUp` to resolve
   - Call `signup(email, password)`
   - Verify `signUp` called with correct args
   - Note: signup doesn't auto-login (requires email verification)

8. **Test logout function**
   - Start in authenticated state
   - Call `logout()`
   - Verify `signOut` called
   - Verify `isAuthenticated` becomes false
   - Verify `idToken` becomes null

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/contexts/AuthContext.test.tsx`
- [ ] Initial state tested
- [ ] Auto-auth on mount tested (success and failure)
- [ ] Login tested (success and failure)
- [ ] Signup tested
- [ ] Logout tested
- [ ] Tests pass: `npm test -- AuthContext`

**Testing Instructions:**
```bash
cd frontend && npm test -- AuthContext
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add AuthContext and AuthProvider tests

- Test initial loading and authentication states
- Test login, signup, logout flows
- Test auto-authentication on mount
- Test error handling
```

---

### Task 5: Test JobCard Component

**Goal:** Test the JobCard component that displays job information with progress bars and action buttons.

**Files to Create:**
- `frontend/src/components/JobCard.test.tsx`

**Prerequisites:**
- Phase 0 Task 1 complete (custom render with Router)

**Implementation Steps:**

1. **Create test job fixture**
   - Factory function to create Job objects with configurable properties
   - Include all required fields from Job interface

2. **Test basic rendering**
   - Render JobCard with sample job
   - Verify job ID is displayed (truncated to 8 chars)
   - Verify created date is formatted correctly
   - Verify status badge is rendered

3. **Test progress bar calculation**
   - Job with 50/100 records: verify 50% width
   - Job with 0 records: verify 0% width
   - Job with 100/100 records: verify 100% width

4. **Test cost progress bar**
   - Job at 50% of budget: verify green color, 50% width
   - Job at 95% of budget: verify orange color (warning)
   - Job with $0 budget: verify no division error

5. **Test View Details link**
   - Verify link points to `/jobs/{job-id}`
   - Use `@testing-library/react` to find link

6. **Test Download button (COMPLETED jobs)**
   - Render with COMPLETED status
   - Verify Download button is visible
   - Verify button click handler (currently TODO in code)

7. **Test Cancel button (RUNNING/QUEUED jobs)**
   - Render with RUNNING status
   - Verify Cancel button is visible
   - Click Cancel button
   - Verify `onDelete` callback called with job ID

8. **Test Delete button (terminal states)**
   - Render with FAILED status
   - Verify Delete button is visible
   - Verify same for CANCELLED and COMPLETED

9. **Test button visibility by status**
   - QUEUED: Cancel visible, Download hidden
   - RUNNING: Cancel visible, Download hidden
   - COMPLETED: Download visible, Delete visible, Cancel hidden
   - FAILED: Delete visible, Cancel hidden, Download hidden
   - CANCELLED: Delete visible

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/components/JobCard.test.tsx`
- [ ] Basic rendering tested
- [ ] Progress calculations tested
- [ ] All button states tested by job status
- [ ] Callback functions tested
- [ ] Tests pass: `npm test -- JobCard`

**Testing Instructions:**
```bash
cd frontend && npm test -- JobCard
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add JobCard component tests

- Test rendering with various job states
- Test progress bar calculations
- Test button visibility by status
- Test callback invocations
```

---

### Task 6: Test StatusBadge Component

**Goal:** Test the StatusBadge component that displays job status with appropriate styling.

**Files to Create:**
- `frontend/src/components/StatusBadge.test.tsx`

**Prerequisites:**
- Phase 0 Task 1 complete

**Implementation Steps:**

1. **Read StatusBadge implementation**
   - Understand how status maps to colors/styles
   - Note all possible status values

2. **Test each status renders correctly**
   - QUEUED: verify text and styling class
   - RUNNING: verify text and styling class
   - COMPLETED: verify text and styling class
   - FAILED: verify text and styling class
   - CANCELLED: verify text and styling class
   - BUDGET_EXCEEDED: verify text and styling class

3. **Test accessibility**
   - Verify status text is readable
   - Verify sufficient color contrast (if applicable)

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/components/StatusBadge.test.tsx`
- [ ] All 6 status values tested
- [ ] Styling classes verified
- [ ] Tests pass: `npm test -- StatusBadge`

**Testing Instructions:**
```bash
cd frontend && npm test -- StatusBadge
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add StatusBadge component tests

- Test rendering for all job status values
- Verify appropriate styling for each status
```

---

### Task 7: Test PrivateRoute Component

**Goal:** Test the PrivateRoute component that protects routes requiring authentication.

**Files to Create:**
- `frontend/src/components/PrivateRoute.test.tsx`

**Prerequisites:**
- Task 4 complete (AuthContext tests establish patterns)

**Implementation Steps:**

1. **Mock useAuth hook**
   - Control `isAuthenticated` and `loading` values

2. **Test loading state**
   - Set `loading: true`
   - Render PrivateRoute with child content
   - Verify loading indicator is shown (or nothing)
   - Verify child content is NOT rendered

3. **Test authenticated access**
   - Set `isAuthenticated: true`, `loading: false`
   - Render PrivateRoute with child content
   - Verify child content IS rendered

4. **Test unauthenticated redirect**
   - Set `isAuthenticated: false`, `loading: false`
   - Render PrivateRoute
   - Verify redirect to login page occurs
   - Use `MemoryRouter` to verify navigation

5. **Test with Outlet (if used)**
   - If PrivateRoute uses React Router's Outlet
   - Verify nested routes render correctly

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/components/PrivateRoute.test.tsx`
- [ ] Loading state tested
- [ ] Authenticated access tested
- [ ] Unauthenticated redirect tested
- [ ] Tests pass: `npm test -- PrivateRoute`

**Testing Instructions:**
```bash
cd frontend && npm test -- PrivateRoute
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add PrivateRoute component tests

- Test loading state handling
- Test authenticated user access
- Test redirect for unauthenticated users
```

---

### Task 8: Test CreateJob Form Interactions

**Goal:** Test key interactions in the CreateJob form component without testing every detail.

**Files to Create:**
- `frontend/src/routes/CreateJob.test.tsx`

**Prerequisites:**
- Tasks 1-4 complete (auth and API mocking patterns)

**Implementation Steps:**

1. **Read CreateJob implementation**
   - Understand form fields and validation
   - Note required fields and submission flow

2. **Mock dependencies**
   - Mock API functions (`createJob`, `generateUploadUrl`)
   - Mock React Query mutations
   - Mock navigation (useNavigate)

3. **Test form renders required fields**
   - Template selection field exists
   - Seed data upload field exists
   - Budget limit field exists
   - Number of records field exists
   - Submit button exists

4. **Test validation feedback**
   - Submit without required fields
   - Verify validation errors appear
   - Note: Don't test every validation rule, just verify feedback mechanism works

5. **Test successful submission**
   - Fill in valid form data
   - Submit form
   - Verify `createJob` called with correct payload
   - Verify navigation to jobs list after success

6. **Test submission error handling**
   - Configure API to reject
   - Submit form
   - Verify error message displayed to user

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/routes/CreateJob.test.tsx`
- [ ] Form fields render tested
- [ ] Basic validation feedback tested
- [ ] Successful submission flow tested
- [ ] Error handling tested
- [ ] Tests pass: `npm test -- CreateJob`

**Testing Instructions:**
```bash
cd frontend && npm test -- CreateJob
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add CreateJob form tests

- Test form field rendering
- Test validation feedback
- Test submission success and error flows
```

---

### Task 9: Test API Service Layer

**Goal:** Test the API service functions that communicate with the backend.

**Files to Create:**
- `frontend/src/services/api.test.ts`

**Prerequisites:**
- Phase 0 Task 1 complete

**Implementation Steps:**

1. **Mock axios**
   - Mock the axios instance created in api.ts
   - Control request/response behavior

2. **Mock auth service**
   - Mock `getIdToken` to return test token

3. **Test fetchJobs**
   - Call `fetchJobs()`
   - Verify GET request to `/jobs`
   - Verify Authorization header includes token
   - Verify returns `data.jobs` array

4. **Test fetchJobDetails**
   - Call `fetchJobDetails('job-123')`
   - Verify GET request to `/jobs/job-123`
   - Verify returns job object

5. **Test createJob**
   - Call `createJob(jobData)`
   - Verify POST request to `/jobs`
   - Verify request body matches input
   - Verify returns created job

6. **Test deleteJob**
   - Call `deleteJob('job-123')`
   - Verify DELETE request to `/jobs/job-123`

7. **Test cancelJob**
   - Call `cancelJob('job-123')`
   - Verify DELETE request to `/jobs/job-123`
   - Note: Same endpoint as delete (verify this is intentional)

8. **Test generateUploadUrl**
   - Call `generateUploadUrl('file.json', 'application/json')`
   - Verify POST request to `/seed-data/upload`
   - Verify returns `{ upload_url, s3_key }`

9. **Test auth interceptor**
   - Verify interceptor adds Authorization header
   - Test when `getIdToken` returns null (no header)
   - Test when `getIdToken` throws (logs error, continues)

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/services/api.test.ts`
- [ ] All exported functions tested
- [ ] Auth interceptor tested
- [ ] Error cases tested
- [ ] Tests pass: `npm test -- api.test`

**Testing Instructions:**
```bash
cd frontend && npm test -- api.test
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add API service tests

- Test all API functions (fetchJobs, createJob, etc.)
- Test auth interceptor behavior
- Test error handling
```

---

### Task 10: Test Auth Service Layer

**Goal:** Test the auth service functions that wrap Cognito SDK.

**Files to Create:**
- `frontend/src/services/auth.test.ts`

**Prerequisites:**
- Phase 0 Task 1 complete (Cognito mock)

**Implementation Steps:**

1. **Mock amazon-cognito-identity-js**
   - Mock `CognitoUserPool`, `CognitoUser`, `AuthenticationDetails`
   - Control callback behaviors (onSuccess, onFailure)

2. **Test signUp**
   - Call `signUp(email, password)`
   - Verify `userPool.signUp` called with correct attributes
   - Test success case (resolves)
   - Test failure case (rejects with error)

3. **Test signIn**
   - Call `signIn(email, password)`
   - Verify `CognitoUser` created with correct username
   - Verify `authenticateUser` called with correct details
   - Test success: verify returns ID token
   - Test failure: verify rejects with error

4. **Test getCurrentUser**
   - Mock `userPool.getCurrentUser()`
   - Verify returns user when exists
   - Verify returns null when no user

5. **Test getIdToken**
   - Mock `getCurrentUser` to return user
   - Mock `user.getSession` to return session
   - Verify returns JWT token string
   - Test when no current user (returns null)
   - Test when getSession fails (rejects)

6. **Test signOut**
   - Mock `getCurrentUser` to return user
   - Call `signOut()`
   - Verify `user.signOut()` called
   - Test when no current user (no error)

**Verification Checklist:**
- [ ] Test file exists at `frontend/src/services/auth.test.ts`
- [ ] signUp tested (success and failure)
- [ ] signIn tested (success and failure)
- [ ] getCurrentUser tested
- [ ] getIdToken tested (all cases)
- [ ] signOut tested
- [ ] Tests pass: `npm test -- auth.test`

**Testing Instructions:**
```bash
cd frontend && npm test -- auth.test
```

**Commit Message Template:**
```
Author & Committer: HatmanStack
Email: 82614182+HatmanStack@users.noreply.github.com

test(frontend): add auth service tests

- Test Cognito SDK wrapper functions
- Test signUp, signIn, signOut flows
- Test token retrieval
```

---

## Phase Verification

**How to verify Phase 1 is complete:**

1. **Run all frontend tests:**
   ```bash
   cd frontend && npm test
   ```
   - All tests should pass
   - No skipped tests (unless intentional)

2. **Check coverage (optional):**
   ```bash
   cd frontend && npm test -- --coverage
   ```
   - Hooks: ~90%+ coverage
   - Contexts: ~90%+ coverage
   - Key components: ~80%+ coverage
   - Services: ~90%+ coverage

3. **Verify in CI:**
   ```bash
   npm run check
   ```
   - Lint passes
   - All tests pass

**Integration Points:**
- Tests use utilities from Phase 0
- Patterns established here inform Phase 2 approach

**Known Limitations:**
- CreateJob tests are focused on key interactions, not exhaustive
- Monaco editor (in TemplateEditor) is not tested (complex external dependency)
- Some components (Layout, Sidebar, Header) are not tested (low value, mostly static)

**Technical Debt:**
- Download button in JobCard has TODO placeholder - tests document current behavior
- cancelJob and deleteJob use same endpoint - tests document this
