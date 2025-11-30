import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider } from './AuthContext.tsx'
import { useAuth } from '../hooks/useAuth'
import * as authService from '../services/auth'

// Mock the auth service
vi.mock('../services/auth', () => ({
  getIdToken: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}))

const mockGetIdToken = vi.mocked(authService.getIdToken)
const mockSignIn = vi.mocked(authService.signIn)
const mockSignUp = vi.mocked(authService.signUp)
const mockSignOut = vi.mocked(authService.signOut)

// Test component that uses auth context
function TestConsumer() {
  const { isAuthenticated, idToken, loading, login, signup, logout } = useAuth()

  return (
    <div>
      <div data-testid="loading">{loading ? 'loading' : 'not-loading'}</div>
      <div data-testid="authenticated">{isAuthenticated ? 'authenticated' : 'not-authenticated'}</div>
      <div data-testid="token">{idToken || 'no-token'}</div>
      <button onClick={() => login('test@example.com', 'password123')}>Login</button>
      <button onClick={() => signup('test@example.com', 'password123')}>Signup</button>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', async () => {
    // Make getIdToken take a while
    mockGetIdToken.mockImplementation(() => new Promise(() => {}))

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    expect(screen.getByTestId('loading')).toHaveTextContent('loading')
    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
  })

  it('auto-authenticates when token exists on mount', async () => {
    mockGetIdToken.mockResolvedValueOnce('existing-token-123')

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('authenticated')
    expect(screen.getByTestId('token')).toHaveTextContent('existing-token-123')
  })

  it('handles failed auto-authentication silently', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGetIdToken.mockRejectedValueOnce(new Error('Session expired'))

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
    expect(screen.getByTestId('token')).toHaveTextContent('no-token')
    expect(consoleSpy).toHaveBeenCalled()

    consoleSpy.mockRestore()
  })

  it('handles no existing token on mount', async () => {
    mockGetIdToken.mockResolvedValueOnce(null)

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
    expect(screen.getByTestId('token')).toHaveTextContent('no-token')
  })

  it('login success updates auth state', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValueOnce(null) // Initial check
    mockSignIn.mockResolvedValueOnce('new-token-456')

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    await user.click(screen.getByText('Login'))

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('authenticated')
    })

    expect(mockSignIn).toHaveBeenCalledWith('test@example.com', 'password123')
    expect(screen.getByTestId('token')).toHaveTextContent('new-token-456')
  })

  it('login failure keeps user unauthenticated', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValueOnce(null)
    mockSignIn.mockRejectedValueOnce(new Error('Invalid credentials'))

    // Component that handles login errors
    function TestConsumerWithErrorHandling() {
      const { isAuthenticated, loading, login } = useAuth()
      const [error, setError] = React.useState<string | null>(null)

      const handleLogin = async () => {
        try {
          await login('test@example.com', 'password123')
        } catch (e) {
          setError((e as Error).message)
        }
      }

      return (
        <div>
          <div data-testid="loading">{loading ? 'loading' : 'not-loading'}</div>
          <div data-testid="authenticated">{isAuthenticated ? 'authenticated' : 'not-authenticated'}</div>
          <div data-testid="error">{error || 'no-error'}</div>
          <button onClick={handleLogin}>Login</button>
        </div>
      )
    }

    render(
      <AuthProvider>
        <TestConsumerWithErrorHandling />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    await user.click(screen.getByText('Login'))

    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('Invalid credentials')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
  })

  it('signup calls auth service', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValueOnce(null)
    mockSignUp.mockResolvedValueOnce()

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading')
    })

    await user.click(screen.getByText('Signup'))

    await waitFor(() => {
      expect(mockSignUp).toHaveBeenCalledWith('test@example.com', 'password123')
    })

    // Note: signup doesn't auto-login (requires email verification)
    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
  })

  it('logout clears auth state', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValueOnce('existing-token')

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('authenticated')
    })

    await user.click(screen.getByText('Logout'))

    expect(mockSignOut).toHaveBeenCalled()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('not-authenticated')
    expect(screen.getByTestId('token')).toHaveTextContent('no-token')
  })
})
