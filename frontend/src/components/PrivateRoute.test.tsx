import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { PrivateRoute } from './PrivateRoute'
import * as useAuthModule from '../hooks/useAuth'

// Mock the useAuth hook
vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

const mockUseAuth = vi.mocked(useAuthModule.useAuth)

describe('PrivateRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderWithRouter = (initialEntry: string = '/protected') => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/protected"
            element={
              <PrivateRoute>
                <div data-testid="protected-content">Protected Content</div>
              </PrivateRoute>
            }
          />
          <Route path="/login" element={<div data-testid="login-page">Login Page</div>} />
        </Routes>
      </MemoryRouter>
    )
  }

  it('shows loading indicator when loading is true', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      idToken: null,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: true,
    })

    renderWithRouter()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      idToken: 'test-token',
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    })

    renderWithRouter()

    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
  })

  it('redirects to /login when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      idToken: null,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    })

    renderWithRouter()

    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('does not show loading indicator when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      idToken: 'test-token',
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    })

    renderWithRouter()

    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
  })

  it('does not show loading indicator when redirecting', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      idToken: null,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    })

    renderWithRouter()

    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
  })
})
