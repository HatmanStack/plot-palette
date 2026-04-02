/**
 * Tests for AuthContext loading timeout behavior.
 *
 * Verifies that checkAuth timeout prevents infinite loading state
 * when auth service is unreachable (health-audit HIGH-10).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'

// Mock auth service
vi.mock('../../services/auth', () => ({
  getIdToken: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}))

import * as authService from '../../services/auth'
import { AuthProvider, AuthContext } from '../../contexts/AuthContext'
import { useContext } from 'react'

// Test component that displays auth state
function AuthStateDisplay() {
  const auth = useContext(AuthContext)
  if (!auth) return <div>No context</div>
  return (
    <div>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
    </div>
  )
}

describe('AuthContext loading timeout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('resolves loading state after timeout when auth service never responds', async () => {
    const mockGetIdToken = vi.mocked(authService.getIdToken)
    // Return a promise that never resolves (simulating offline auth service)
    mockGetIdToken.mockReturnValue(new Promise(() => {}))

    await act(async () => {
      render(
        <AuthProvider>
          <AuthStateDisplay />
        </AuthProvider>
      )
    })

    // Initially loading should be true
    expect(screen.getByTestId('loading').textContent).toBe('true')

    // Advance past the timeout (10 seconds)
    await act(async () => {
      vi.advanceTimersByTime(11000)
    })

    // After timeout, loading should be false and user should be unauthenticated
    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('authenticated').textContent).toBe('false')
  })

  it('resolves normally when auth check succeeds before timeout', async () => {
    const mockGetIdToken = vi.mocked(authService.getIdToken)
    mockGetIdToken.mockResolvedValue('valid-token')

    await act(async () => {
      render(
        <AuthProvider>
          <AuthStateDisplay />
        </AuthProvider>
      )
    })

    // Should resolve immediately without waiting for timeout
    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('authenticated').textContent).toBe('true')
  })
})
