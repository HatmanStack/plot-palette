# Phase 6: React Frontend Application

## Phase Goal

Build the complete React web application using Vite that provides users with an intuitive interface for managing generation jobs, creating templates, uploading seed data, and monitoring real-time progress. By the end of this phase, users can interact with all backend functionality through a modern, responsive UI hosted on AWS Amplify.

**Success Criteria:**
- React app bootstrapped with Vite and TypeScript
- Authentication UI (login, signup, password reset)
- Dashboard showing all user's jobs with status
- Job creation wizard with validation
- Template editor with syntax highlighting and testing
- Seed data upload interface
- Real-time job monitoring with progress bars and cost tracking
- Responsive design (mobile-friendly)
- Deployed to AWS Amplify with CI/CD
- Environment configuration for API endpoint and Cognito

**Estimated Tokens:** ~110,000

---

## Prerequisites

- **Phases 1-5** completed (all backend APIs functional)
- **Phase 2** Cognito and API Gateway deployed
- Node.js 20+ and npm installed
- Basic understanding of React, TypeScript, and modern frontend tooling

---

## Task 1: Project Setup and Routing

### Goal

Bootstrap React application with Vite, TypeScript, React Router, and base project structure.

### Files to Create

- `frontend/package.json` - Dependencies
- `frontend/vite.config.ts` - Vite configuration
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/src/main.tsx` - Entry point
- `frontend/src/App.tsx` - Root component with routing
- `frontend/src/routes/*` - Route components
- `frontend/index.html` - HTML template

### Prerequisites

- Node.js and npm installed
- Familiarity with Vite and React Router

### Implementation Steps

1. **Initialize Vite project:**
   ```bash
   cd frontend
   npm create vite@latest . -- --template react-ts
   ```

2. **Install dependencies:**
   ```bash
   npm install react-router-dom @tanstack/react-query axios
   npm install -D @types/node tailwindcss postcss autoprefixer
   npx tailwindcss init -p
   ```

3. **Configure Tailwind CSS** (`tailwind.config.js`):
   ```js
   export default {
     content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
     theme: {
       extend: {},
     },
     plugins: [],
   }
   ```

4. **Create environment configuration** (`.env`):
   ```
   VITE_API_ENDPOINT=https://api-id.execute-api.us-east-1.amazonaws.com
   VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
   VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXX
   VITE_REGION=us-east-1
   ```

5. **Create routing structure** (`src/App.tsx`):
   ```tsx
   import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
   import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
   import { AuthProvider } from './contexts/AuthContext'
   import { PrivateRoute } from './components/PrivateRoute'
   import Login from './routes/Login'
   import Signup from './routes/Signup'
   import Dashboard from './routes/Dashboard'
   import Jobs from './routes/Jobs'
   import JobDetail from './routes/JobDetail'
   import Templates from './routes/Templates'
   import TemplateEditor from './routes/TemplateEditor'
   import Settings from './routes/Settings'
   import Layout from './components/Layout'

   const queryClient = new QueryClient()

   function App() {
     return (
       <QueryClientProvider client={queryClient}>
         <AuthProvider>
           <BrowserRouter>
             <Routes>
               <Route path="/login" element={<Login />} />
               <Route path="/signup" element={<Signup />} />

               <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
                 <Route path="/" element={<Navigate to="/dashboard" replace />} />
                 <Route path="/dashboard" element={<Dashboard />} />
                 <Route path="/jobs" element={<Jobs />} />
                 <Route path="/jobs/:jobId" element={<JobDetail />} />
                 <Route path="/templates" element={<Templates />} />
                 <Route path="/templates/new" element={<TemplateEditor />} />
                 <Route path="/templates/:templateId" element={<TemplateEditor />} />
                 <Route path="/settings" element={<Settings />} />
               </Route>
             </Routes>
           </BrowserRouter>
         </AuthProvider>
       </QueryClientProvider>
     )
   }

   export default App
   ```

6. **Create base layout component** (`src/components/Layout.tsx`):
   ```tsx
   import { Outlet } from 'react-router-dom'
   import Sidebar from './Sidebar'
   import Header from './Header'

   export default function Layout() {
     return (
       <div className="flex h-screen bg-gray-50">
         <Sidebar />
         <div className="flex-1 flex flex-col">
           <Header />
           <main className="flex-1 overflow-y-auto p-6">
             <Outlet />
           </main>
         </div>
       </div>
     )
   }
   ```

### Verification Checklist

- [ ] Vite dev server starts without errors
- [ ] TypeScript compilation successful
- [ ] Routing configured
- [ ] Tailwind CSS working
- [ ] Environment variables loaded
- [ ] Base layout renders

### Testing Instructions

```bash
cd frontend
npm install
npm run dev

# Open http://localhost:5173
# Should see routing working (blank pages for now)
```

### Commit Message Template

```
feat(frontend): initialize React app with Vite and routing

- Bootstrap React + TypeScript project with Vite
- Configure Tailwind CSS for styling
- Set up React Router with authenticated routes
- Create base layout with sidebar and header
- Add environment configuration for API and Cognito
- Install React Query for data fetching

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~15,000

---

## Task 2: Authentication (Login, Signup)

### Goal

Implement authentication UI components that integrate with AWS Cognito for login, signup, and session management.

### Files to Create

- `src/contexts/AuthContext.tsx` - Auth state management
- `src/services/auth.ts` - Cognito API calls
- `src/routes/Login.tsx` - Login page
- `src/routes/Signup.tsx` - Signup page
- `src/components/PrivateRoute.tsx` - Protected route wrapper

### Prerequisites

- Task 1 completed (routing setup)
- AWS Cognito User Pool configured (Phase 2)

### Implementation Steps

1. **Install AWS Amplify libraries:**
   ```bash
   npm install amazon-cognito-identity-js
   ```

2. **Create auth service** (`src/services/auth.ts`):
   ```ts
   import {
     CognitoUserPool,
     CognitoUser,
     AuthenticationDetails,
     CognitoUserAttribute
   } from 'amazon-cognito-identity-js'

   const userPool = new CognitoUserPool({
     UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
     ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID
   })

   export async function signUp(email: string, password: string): Promise<void> {
     return new Promise((resolve, reject) => {
       const attributeList = [
         new CognitoUserAttribute({ Name: 'email', Value: email })
       ]

       userPool.signUp(email, password, attributeList, [], (err, result) => {
         if (err) reject(err)
         else resolve()
       })
     })
   }

   export async function signIn(email: string, password: string): Promise<string> {
     return new Promise((resolve, reject) => {
       const user = new CognitoUser({ Username: email, Pool: userPool })

       const authDetails = new AuthenticationDetails({
         Username: email,
         Password: password
       })

       user.authenticateUser(authDetails, {
         onSuccess: (session) => {
           const idToken = session.getIdToken().getJwtToken()
           resolve(idToken)
         },
         onFailure: (err) => reject(err)
       })
     })
   }

   export function getCurrentUser(): CognitoUser | null {
     return userPool.getCurrentUser()
   }

   export async function getIdToken(): Promise<string | null> {
     const user = getCurrentUser()
     if (!user) return null

     return new Promise((resolve, reject) => {
       user.getSession((err: any, session: any) => {
         if (err) reject(err)
         else resolve(session.getIdToken().getJwtToken())
       })
     })
   }

   export function signOut(): void {
     const user = getCurrentUser()
     if (user) user.signOut()
   }
   ```

3. **Create AuthContext** (`src/contexts/AuthContext.tsx`):
   ```tsx
   import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
   import * as authService from '../services/auth'

   interface AuthContextType {
     isAuthenticated: boolean
     idToken: string | null
     login: (email: string, password: string) => Promise<void>
     signup: (email: string, password: string) => Promise<void>
     logout: () => void
     loading: boolean
   }

   const AuthContext = createContext<AuthContextType | undefined>(undefined)

   export function AuthProvider({ children }: { children: ReactNode }) {
     const [isAuthenticated, setIsAuthenticated] = useState(false)
     const [idToken, setIdToken] = useState<string | null>(null)
     const [loading, setLoading] = useState(true)

     useEffect(() => {
       checkAuth()
     }, [])

     async function checkAuth() {
       try {
         const token = await authService.getIdToken()
         if (token) {
           setIdToken(token)
           setIsAuthenticated(true)
         }
       } catch (error) {
         console.error('Auth check failed:', error)
       } finally {
         setLoading(false)
       }
     }

     async function login(email: string, password: string) {
       const token = await authService.signIn(email, password)
       setIdToken(token)
       setIsAuthenticated(true)
     }

     async function signup(email: string, password: string) {
       await authService.signUp(email, password)
       // Note: Cognito requires email verification before login
     }

     function logout() {
       authService.signOut()
       setIdToken(null)
       setIsAuthenticated(false)
     }

     return (
       <AuthContext.Provider value={{ isAuthenticated, idToken, login, signup, logout, loading }}>
         {children}
       </AuthContext.Provider>
     )
   }

   export function useAuth() {
     const context = useContext(AuthContext)
     if (!context) throw new Error('useAuth must be used within AuthProvider')
     return context
   }
   ```

4. **Create Login page** (`src/routes/Login.tsx`):
   ```tsx
   import { useState } from 'react'
   import { useNavigate, Link } from 'react-router-dom'
   import { useAuth } from '../contexts/AuthContext'

   export default function Login() {
     const [email, setEmail] = useState('')
     const [password, setPassword] = useState('')
     const [error, setError] = useState('')
     const [loading, setLoading] = useState(false)
     const { login } = useAuth()
     const navigate = useNavigate()

     async function handleSubmit(e: React.FormEvent) {
       e.preventDefault()
       setError('')
       setLoading(true)

       try {
         await login(email, password)
         navigate('/dashboard')
       } catch (err: any) {
         setError(err.message || 'Failed to login')
       } finally {
         setLoading(false)
       }
     }

     return (
       <div className="min-h-screen flex items-center justify-center bg-gray-50">
         <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
           <div>
             <h2 className="text-3xl font-bold text-center">Plot Palette</h2>
             <p className="mt-2 text-center text-gray-600">Sign in to your account</p>
           </div>

           <form onSubmit={handleSubmit} className="space-y-6">
             {error && (
               <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
                 {error}
               </div>
             )}

             <div>
               <label className="block text-sm font-medium text-gray-700">Email</label>
               <input
                 type="email"
                 value={email}
                 onChange={(e) => setEmail(e.target.value)}
                 required
                 className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
               />
             </div>

             <div>
               <label className="block text-sm font-medium text-gray-700">Password</label>
               <input
                 type="password"
                 value={password}
                 onChange={(e) => setPassword(e.target.value)}
                 required
                 className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
               />
             </div>

             <button
               type="submit"
               disabled={loading}
               className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
             >
               {loading ? 'Signing in...' : 'Sign in'}
             </button>

             <p className="text-center text-sm text-gray-600">
               Don't have an account?{' '}
               <Link to="/signup" className="text-blue-600 hover:underline">Sign up</Link>
             </p>
           </form>
         </div>
       </div>
     )
   }
   ```

5. **Create Signup page** (similar structure to Login)

6. **Create PrivateRoute component** (`src/components/PrivateRoute.tsx`):
   ```tsx
   import { Navigate } from 'react-router-dom'
   import { useAuth } from '../contexts/AuthContext'

   export function PrivateRoute({ children }: { children: React.ReactNode }) {
     const { isAuthenticated, loading } = useAuth()

     if (loading) {
       return <div className="flex items-center justify-center h-screen">Loading...</div>
     }

     return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
   }
   ```

### Verification Checklist

- [ ] Login form works with Cognito
- [ ] Signup form works
- [ ] AuthContext manages session
- [ ] PrivateRoute redirects to login if not authenticated
- [ ] Token stored and retrieved correctly
- [ ] Logout clears session
- [ ] Error messages display properly

### Testing Instructions

```bash
# Test signup
# 1. Navigate to /signup
# 2. Enter email and password (12+ chars)
# 3. Should receive confirmation (check email for verification)

# Test login (after email verification)
# 1. Navigate to /login
# 2. Enter credentials
# 3. Should redirect to /dashboard

# Test protected routes
# 1. Logout
# 2. Try to access /dashboard
# 3. Should redirect to /login
```

### Commit Message Template

```
feat(frontend): add authentication UI with Cognito integration

- Create auth service for Cognito signup/login/logout
- Implement AuthContext for session management
- Build Login and Signup pages with form validation
- Add PrivateRoute component for protected routes
- Handle auth errors and loading states
- Store and refresh JWT tokens

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~18,000

---

## Task 3: Dashboard - Job List

### Goal

Create dashboard showing user's jobs with status, progress, and quick actions.

### Files to Create

- `src/routes/Dashboard.tsx` - Dashboard page
- `src/components/JobCard.tsx` - Individual job card component
- `src/components/StatusBadge.tsx` - Job status badge
- `src/hooks/useJobs.ts` - Custom hook for fetching jobs
- `src/services/api.ts` - API client functions

### Prerequisites

- Tasks 1-2 completed (routing and auth)
- Phase 3 API endpoints deployed

### Implementation Steps

1. **Create API client** (`src/services/api.ts`):
   ```typescript
   import axios from 'axios'

   const apiClient = axios.create({
     baseURL: import.meta.env.VITE_API_ENDPOINT,
   })

   // Add auth token to all requests
   apiClient.interceptors.request.use((config) => {
     const token = localStorage.getItem('idToken')
     if (token) {
       config.headers.Authorization = `Bearer ${token}`
     }
     return config
   })

   export async function fetchJobs() {
     const { data } = await apiClient.get('/jobs')
     return data
   }

   export async function createJob(jobData: any) {
     const { data } = await apiClient.post('/jobs', jobData)
     return data
   }

   export async function deleteJob(jobId: string) {
     await apiClient.delete(`/jobs/${jobId}`)
   }
   ```

2. **Create useJobs hook** (`src/hooks/useJobs.ts`):
   ```typescript
   import { useQuery } from '@tanstack/react-query'
   import { fetchJobs } from '../services/api'

   export function useJobs() {
     return useQuery({
       queryKey: ['jobs'],
       queryFn: fetchJobs,
       refetchInterval: 10000, // Refetch every 10 seconds for live updates
     })
   }
   ```

3. **Create StatusBadge component** - Color-coded badges for job states:
   - QUEUED: gray
   - RUNNING: blue (animated pulse)
   - COMPLETED: green
   - FAILED: red
   - CANCELLED: yellow
   - BUDGET_EXCEEDED: orange

4. **Create JobCard component** - Display:
   - Job name and ID
   - Status badge
   - Progress bar (records_completed / total_records)
   - Cost ($X.XX / $Y.YY budget)
   - Created/updated timestamps
   - Actions: View details, Cancel, Delete

5. **Create Dashboard page** - Features:
   - Grid/list view of job cards
   - Filter dropdown (All, Running, Completed, Failed)
   - Sort by (Created date, Status, Cost)
   - "Create New Job" button
   - Empty state when no jobs
   - Loading skeleton

### Verification Checklist

- [ ] Dashboard fetches and displays user's jobs
- [ ] Status badges show correct colors
- [ ] Progress bars update in real-time
- [ ] Cost tracking displays correctly
- [ ] Filter and sort work
- [ ] Create job button navigates to wizard
- [ ] Delete job works with confirmation

### Testing Instructions

```bash
# Run dev server
npm run dev

# Create test jobs via API
curl -X POST $API_ENDPOINT/jobs -H "Authorization: Bearer $TOKEN" -d '...'

# Verify dashboard shows jobs
# Test filtering and sorting
# Test delete with confirmation modal
```

### Commit Message Template

```
feat(frontend): add job dashboard with real-time updates

- Create dashboard page with job list
- Add StatusBadge component with color coding
- Implement JobCard component with progress and cost
- Add useJobs hook with auto-refresh
- Create API client with auth interceptor
- Add filter and sort functionality

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~12,000

---

## Task 4: Job Creation Wizard

### Goal

Multi-step wizard for creating jobs with template selection, seed data upload, and configuration.

### Files to Create

- `src/routes/CreateJob.tsx` - Multi-step wizard
- `src/components/wizard/StepIndicator.tsx` - Step progress indicator
- `src/components/wizard/TemplateSelector.tsx` - Template selection step
- `src/components/wizard/SeedDataUpload.tsx` - File upload step
- `src/components/wizard/JobConfiguration.tsx` - Configuration step
- `src/components/wizard/ReviewAndCreate.tsx` - Final review step

### Prerequisites

- Task 3 completed (API client)
- Phase 3 template and job APIs available
- File upload functionality

### Implementation Steps

1. **Create wizard state management:**
   ```typescript
   const [currentStep, setCurrentStep] = useState(1)
   const [wizardData, setWizardData] = useState({
     template_id: '',
     seed_data_file: null,
     budget_limit: 10,
     num_records: 100,
     output_format: 'JSONL'
   })
   ```

2. **Step 1: Template Selection**
   - Fetch templates from API (system + user templates)
   - Display as cards with name, description, preview
   - Search and filter functionality
   - "Create New Template" option

3. **Step 2: Seed Data Upload**
   - Drag-and-drop file upload
   - Support CSV, JSONL formats
   - File validation (check headers match template variables)
   - Preview first 5 rows
   - Upload to S3 via presigned URL (from API)

4. **Step 3: Job Configuration**
   - Budget limit input (with slider, $1-$1000)
   - Number of records (with validation against seed data)
   - Output format dropdown (JSONL, CSV, Parquet)
   - Model preferences (optional)

5. **Step 4: Review and Create**
   - Display all selections
   - Cost estimate (call API endpoint)
   - Edit buttons for each section
   - "Create Job" button (POST to /jobs)
   - Loading state while creating
   - Redirect to job detail page on success

6. **Navigation:**
   - Next/Previous buttons
   - Step validation before advancing
   - Progress indicator showing 1/4, 2/4, etc.

### Verification Checklist

- [ ] All four steps functional
- [ ] Template selection works
- [ ] File upload accepts CSV/JSONL
- [ ] File validation checks format
- [ ] Budget and records inputs validated
- [ ] Review step shows all data
- [ ] Job creation successful
- [ ] Redirects to job detail after creation

### Testing Instructions

```bash
# Test wizard flow
# 1. Navigate to /jobs/new
# 2. Select template
# 3. Upload sample CSV
# 4. Set budget to $5, 50 records
# 5. Review and create
# 6. Verify redirect to /jobs/{id}
```

### Commit Message Template

```
feat(frontend): add multi-step job creation wizard

- Create 4-step wizard for job creation
- Implement template selection with search
- Add drag-and-drop seed data upload
- Build job configuration form with validation
- Create review step with cost estimation
- Add step navigation and progress indicator

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~14,000

---

## Task 5: Job Detail & Real-time Monitoring

### Goal

Job detail page with real-time updates and progress visualization.

### Files to Create

- `src/routes/JobDetail.tsx` - Job detail page
- `src/components/ProgressChart.tsx` - Progress visualization
- `src/components/CostBreakdown.tsx` - Cost breakdown chart
- `src/hooks/useJobPolling.ts` - Polling hook for live updates

### Prerequisites

- Task 3 completed (API client)
- Phase 3 dashboard API endpoint

### Implementation Steps

1. **Create useJobPolling hook:**
   ```typescript
   export function useJobPolling(jobId: string) {
     return useQuery({
       queryKey: ['job', jobId],
       queryFn: () => fetchJobDetails(jobId),
       refetchInterval: (data) => {
         // Poll every 5 seconds if job is RUNNING or QUEUED
         if (data?.status === 'RUNNING' || data?.status === 'QUEUED') {
           return 5000
         }
         return false // Don't poll if job is complete
       },
     })
   }
   ```

2. **Job Detail Page** - Display:
   - Job ID and name
   - Status badge (with animation for RUNNING)
   - Progress bar with percentage
   - Records completed vs total
   - Current cost vs budget
   - Estimated time remaining
   - Created/started/completed timestamps

3. **Progress Chart** - Visualization:
   - Line chart showing records over time
   - Use Recharts or Chart.js
   - X-axis: time, Y-axis: records completed
   - Show checkpoint markers

4. **Cost Breakdown** - Display:
   - Total cost so far
   - Cost per model (if using multiple)
   - Budget remaining
   - Pie chart or bar chart

5. **Actions Section:**
   - Download export button (enabled when COMPLETED)
   - Cancel job button (enabled when RUNNING/QUEUED)
   - Delete job button (with confirmation)
   - View logs button (link to CloudWatch)

6. **Export Downloads:**
   - Fetch presigned S3 URLs from API
   - Download links for JSONL, CSV, Parquet
   - File size indicators

### Verification Checklist

- [ ] Job details fetched and displayed
- [ ] Real-time updates work (5-second polling)
- [ ] Progress chart shows data
- [ ] Cost breakdown accurate
- [ ] Cancel job works
- [ ] Download exports work
- [ ] Polling stops when job complete

### Testing Instructions

```bash
# Create and monitor a job
# Navigate to /jobs/{id}
# Verify real-time updates
# Wait for completion
# Download exports
# Verify file contents
```

### Commit Message Template

```
feat(frontend): add job detail page with real-time monitoring

- Create job detail page with polling
- Implement progress chart with Recharts
- Add cost breakdown visualization
- Build export download functionality
- Add cancel and delete actions
- Implement 5-second polling for live updates

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~13,000

---

## Task 6: Template Editor

### Goal

Template editor with syntax highlighting, validation, and testing.

### Files to Create

- `src/routes/TemplateEditor.tsx` - Template editor page
- `src/components/CodeEditor.tsx` - Monaco/CodeMirror wrapper
- `src/components/TemplatePreview.tsx` - Live preview component
- `src/hooks/useTemplateValidation.ts` - Validation hook

### Prerequisites

- Task 3 completed
- Phase 5 template engine deployed
- Monaco Editor or CodeMirror library

### Implementation Steps

1. **Install editor library:**
   ```bash
   npm install @monaco-editor/react
   # OR
   npm install @uiw/react-codemirror @codemirror/lang-yaml
   ```

2. **Create CodeEditor component:**
   - Configure for YAML syntax
   - Enable syntax highlighting
   - Add auto-completion (template variables, custom filters)
   - Error highlighting for invalid YAML

3. **Template Editor Page Layout:**
   - Split view: Editor on left, Preview on right
   - Template name input
   - Description textarea
   - Save/Update button
   - Test template button

4. **Template Validation:**
   - Validate YAML syntax client-side
   - Validate template structure (required fields: steps, model)
   - Check variable references
   - Warn about undefined variables

5. **Template Testing:**
   - "Test Template" button
   - Modal with sample seed data input
   - Call POST /templates/{id}/test API
   - Display rendered prompt
   - Show any errors

6. **Save/Update Flow:**
   - POST /templates for new templates
   - PUT /templates/{id} for updates
   - Success message with redirect
   - Error handling

### Verification Checklist

- [ ] Editor loads with syntax highlighting
- [ ] YAML validation works
- [ ] Auto-completion functional
- [ ] Template testing works
- [ ] Save creates new template
- [ ] Update modifies existing template
- [ ] Error messages clear

### Testing Instructions

```bash
# Create new template
# Navigate to /templates/new
# Write YAML template
# Test with sample data
# Save template
# Edit existing template
# Verify changes saved
```

### Commit Message Template

```
feat(frontend): add template editor with Monaco

- Integrate Monaco editor for YAML editing
- Add syntax highlighting and validation
- Implement template testing with preview
- Build save/update functionality
- Add auto-completion for template variables
- Create split-view editor layout

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~13,000

---

## Task 7: Deployment to AWS Amplify

### Goal

Deploy React frontend to AWS Amplify with CI/CD integration.

### Files to Create

- `infrastructure/cloudformation/amplify-stack.yaml` - Amplify app
- `amplify.yml` - Build configuration
- `infrastructure/scripts/deploy-frontend.sh` - Deployment script

### Prerequisites

- Tasks 1-6 completed (frontend working locally)
- AWS Amplify service access
- GitHub repository (optional for CI/CD)

### Implementation Steps

1. **Create Amplify CloudFormation stack:**
   ```yaml
   Resources:
     AmplifyApp:
       Type: AWS::Amplify::App
       Properties:
         Name: plot-palette
         Repository: https://github.com/user/repo  # Optional
         BuildSpec: |
           version: 1
           frontend:
             phases:
               preBuild:
                 commands:
                   - cd frontend
                   - npm install
               build:
                 commands:
                   - npm run build
             artifacts:
               baseDirectory: frontend/dist
               files:
                 - '**/*'
             cache:
               paths:
                 - node_modules/**/*
         EnvironmentVariables:
           - Name: VITE_API_ENDPOINT
             Value: !Ref ApiEndpoint
           - Name: VITE_COGNITO_USER_POOL_ID
             Value: !Ref UserPoolId
           - Name: VITE_COGNITO_CLIENT_ID
             Value: !Ref UserPoolClientId
   ```

2. **Create amplify.yml** (build configuration):
   - Define build phases
   - Specify artifact directory (dist)
   - Set environment variables

3. **Manual deployment option:**
   - Build locally: `npm run build`
   - Deploy via AWS CLI:
     ```bash
     aws amplify create-deployment --app-id $APP_ID --branch-name main
     ```
   - Upload build artifacts to S3
   - Trigger deployment

4. **Configure custom domain** (optional):
   - Add domain in Amplify console
   - Update DNS records
   - Enable HTTPS

5. **Environment variables:**
   - Set API endpoint from CloudFormation outputs
   - Set Cognito pool ID and client ID
   - Configure per environment (dev, staging, prod)

### Verification Checklist

- [ ] Amplify app created
- [ ] Build succeeds
- [ ] Environment variables set
- [ ] App deployed and accessible
- [ ] Custom domain configured (if applicable)
- [ ] CI/CD triggers on git push (if configured)

### Testing Instructions

```bash
# Deploy frontend
./infrastructure/scripts/deploy-frontend.sh production

# Access app
open https://main.xxxxx.amplifyapp.com

# Test authentication
# Test job creation
# Verify API connectivity
```

### Commit Message Template

```
feat(infrastructure): deploy frontend to AWS Amplify

- Create Amplify CloudFormation stack
- Configure build specification
- Set environment variables from stack outputs
- Add deployment script
- Enable HTTPS and custom domain
- Configure CI/CD from GitHub

Author: HatmanStack <82614182+HatmanStack@users.noreply.github.com>
```

**Estimated Tokens:** ~10,000

---

## Phase 6 Verification

**Success Criteria:**

- [ ] React app bootstrapped with Vite and TypeScript
- [ ] Authentication UI works (login, signup, logout)
- [ ] Dashboard displays all user jobs
- [ ] Status badges and progress bars update in real-time
- [ ] Job creation wizard functional (4 steps)
- [ ] Template editor saves and updates templates
- [ ] Job detail page shows real-time progress
- [ ] Export downloads work for all formats
- [ ] Frontend deployed to AWS Amplify
- [ ] Environment variables configured correctly
- [ ] Responsive design on mobile

**Estimated Total Tokens:** ~95,000

**Estimated Monthly Cost:**
- Amplify hosting: ~$1-2/month
- CloudFront: included in Amplify
- Total: ~$2/month

---

**Navigation:**
- [← Previous: Phase 5](./Phase-5.md)
- [Next: Phase 7 - CloudFormation Nested Stacks →](./Phase-7.md)
