import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAuth } from './useAuth'
import { AuthContext } from '../contexts/AuthContext'
import type { AuthContextType } from '../contexts/AuthContext'
import type { ReactNode } from 'react'

describe('useAuth', () => {
  it('throws error when used outside AuthProvider', () => {
    // Suppress console.error for this test since we expect an error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within AuthProvider')

    consoleSpy.mockRestore()
  })

  it('returns context values when inside AuthProvider', () => {
    const mockContext: AuthContextType = {
      isAuthenticated: true,
      idToken: 'test-token-123',
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    }

    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuthContext.Provider value={mockContext}>
        {children}
      </AuthContext.Provider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.idToken).toBe('test-token-123')
    expect(result.current.loading).toBe(false)
    expect(result.current.login).toBe(mockContext.login)
    expect(result.current.signup).toBe(mockContext.signup)
    expect(result.current.logout).toBe(mockContext.logout)
  })

  it('returns unauthenticated state correctly', () => {
    const mockContext: AuthContextType = {
      isAuthenticated: false,
      idToken: null,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: false,
    }

    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuthContext.Provider value={mockContext}>
        {children}
      </AuthContext.Provider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.idToken).toBeNull()
  })

  it('returns loading state correctly', () => {
    const mockContext: AuthContextType = {
      isAuthenticated: false,
      idToken: null,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      loading: true,
    }

    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuthContext.Provider value={mockContext}>
        {children}
      </AuthContext.Provider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    expect(result.current.loading).toBe(true)
  })
})
