import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { PrivateRoute } from './components/PrivateRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './contexts/ToastContext'
import Login from './routes/Login'
import Signup from './routes/Signup'
import Dashboard from './routes/Dashboard'
import Jobs from './routes/Jobs'
import CreateJob from './routes/CreateJob'
import JobDetail from './routes/JobDetail'
import Templates from './routes/Templates'
import TemplateEditor from './routes/TemplateEditor'
import Settings from './routes/Settings'
import Layout from './components/Layout'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />

              <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/jobs/new" element={<CreateJob />} />
                <Route path="/jobs/:jobId" element={<JobDetail />} />
                <Route path="/templates" element={<Templates />} />
                <Route path="/templates/new" element={<TemplateEditor />} />
                <Route path="/templates/:templateId" element={<TemplateEditor />} />
                <Route path="/settings" element={<Settings />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
