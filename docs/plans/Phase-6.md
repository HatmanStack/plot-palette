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

(Due to length, I'll create a more concise version of the remaining tasks for Phase 6, then complete Phases 7-9)

## Task 3: Dashboard - Job List

### Goal

Create dashboard showing user's jobs with status, progress, and quick actions.

**Key Components:**
- Job list table/cards
- Status badges (QUEUED, RUNNING, COMPLETED, etc.)
- Progress bars
- Cost summary
- Filter by status
- Create new job button

**Estimated Tokens:** ~15,000

---

## Task 4: Job Creation Wizard

### Goal

Multi-step wizard for creating jobs with template selection, seed data upload, and configuration.

**Steps:**
1. Select template (from library or user's templates)
2. Upload/select seed data
3. Configure job (budget, records, format)
4. Review and create

**Estimated Tokens:** ~18,000

---

## Task 5: Job Detail & Real-time Monitoring

### Goal

Job detail page with real-time updates using polling or websockets.

**Features:**
- Progress chart
- Cost breakdown visualization
- Live updates (every 5 seconds)
- Download exports
- Cancel/delete job

**Estimated Tokens:** ~16,000

---

## Task 6: Template Editor

### Goal

Template editor with syntax highlighting, validation, and testing.

**Features:**
- Monaco editor or CodeMirror for YAML
- Syntax highlighting
- Real-time validation
- Test template with sample data
- Save/update template

**Estimated Tokens:** ~17,000

---

## Task 7: Deployment to AWS Amplify

### Goal

Deploy frontend to Amplify with CI/CD.

**Steps:**
- Create Amplify app via CloudFormation
- Configure build settings
- Connect to Git (optional)
- Set environment variables
- Deploy

**Estimated Tokens:** ~11,000

---

## Phase 6 Verification

**Success Criteria:**
- [ ] Authentication works end-to-end
- [ ] Dashboard displays jobs
- [ ] Job creation wizard functional
- [ ] Real-time monitoring updates
- [ ] Template editor saves/updates
- [ ] Deployed to Amplify
- [ ] Responsive on mobile

**Estimated Total Cost:**
- Amplify hosting: ~$1-2/month
- CloudFront: included in Amplify

---

**Navigation:**
- [← Previous: Phase 5](./Phase-5.md)
- [Next: Phase 7 - CloudFormation Nested Stacks →](./Phase-7.md)
