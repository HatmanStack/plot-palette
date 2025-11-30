import { describe, it, expect, vi, beforeEach, Mock } from 'vitest'

// Mock setup before imports
const mockFns = {
  signUp: null as Mock | null,
  authenticateUser: null as Mock | null,
  getCurrentUser: null as Mock | null,
  signOut: null as Mock | null,
  getSession: null as Mock | null,
}

vi.mock('amazon-cognito-identity-js', async (importOriginal) => {
  // Get the original module to reference types only
  const _actual = await importOriginal<typeof import('amazon-cognito-identity-js')>()

  return {
    CognitoUserPool: class {
      signUp(...args: unknown[]) {
        return mockFns.signUp?.(...args)
      }
      getCurrentUser() {
        return mockFns.getCurrentUser?.()
      }
    },
    CognitoUser: class {
      authenticateUser(...args: unknown[]) {
        return mockFns.authenticateUser?.(...args)
      }
      getSession(...args: unknown[]) {
        return mockFns.getSession?.(...args)
      }
      signOut() {
        return mockFns.signOut?.()
      }
    },
    AuthenticationDetails: class {
      constructor() {}
    },
    CognitoUserAttribute: class {
      constructor() {}
    },
  }
})

// Import after mocking
import { signUp, signIn, getCurrentUser, getIdToken, signOut } from './auth'

describe('Auth Service', () => {
  beforeEach(() => {
    // Reset all mock functions
    mockFns.signUp = vi.fn()
    mockFns.authenticateUser = vi.fn()
    mockFns.getCurrentUser = vi.fn()
    mockFns.signOut = vi.fn()
    mockFns.getSession = vi.fn()
  })

  describe('signUp', () => {
    it('resolves on successful signup', async () => {
      mockFns.signUp!.mockImplementation(
        (_email: string, _password: string, _attrs: unknown[], _validation: unknown[], callback: (err: null, result: unknown) => void) => {
          callback(null, { user: {} })
        }
      )

      await expect(signUp('test@example.com', 'password123')).resolves.toBeUndefined()
      expect(mockFns.signUp).toHaveBeenCalled()
    })

    it('rejects on signup error', async () => {
      const error = new Error('User already exists')
      mockFns.signUp!.mockImplementation(
        (_email: string, _password: string, _attrs: unknown[], _validation: unknown[], callback: (err: Error) => void) => {
          callback(error)
        }
      )

      await expect(signUp('test@example.com', 'password123')).rejects.toThrow('User already exists')
    })
  })

  describe('signIn', () => {
    it('returns ID token on successful authentication', async () => {
      const mockToken = 'mock-jwt-token-123'
      mockFns.authenticateUser!.mockImplementation(
        (_authDetails: unknown, callbacks: { onSuccess: (session: unknown) => void }) => {
          callbacks.onSuccess({
            getIdToken: () => ({
              getJwtToken: () => mockToken,
            }),
          })
        }
      )

      const result = await signIn('test@example.com', 'password123')

      expect(result).toBe(mockToken)
      expect(mockFns.authenticateUser).toHaveBeenCalled()
    })

    it('rejects on authentication failure', async () => {
      const error = new Error('Incorrect username or password')
      mockFns.authenticateUser!.mockImplementation(
        (_authDetails: unknown, callbacks: { onFailure: (err: Error) => void }) => {
          callbacks.onFailure(error)
        }
      )

      await expect(signIn('test@example.com', 'wrongpassword')).rejects.toThrow('Incorrect username or password')
    })
  })

  describe('getCurrentUser', () => {
    it('returns user when exists', () => {
      const mockUser = { username: 'test@example.com' }
      mockFns.getCurrentUser!.mockReturnValue(mockUser)

      const result = getCurrentUser()

      expect(result).toBe(mockUser)
    })

    it('returns null when no user', () => {
      mockFns.getCurrentUser!.mockReturnValue(null)

      const result = getCurrentUser()

      expect(result).toBeNull()
    })
  })

  describe('getIdToken', () => {
    it('returns null when no current user', async () => {
      mockFns.getCurrentUser!.mockReturnValue(null)

      const result = await getIdToken()

      expect(result).toBeNull()
    })

    it('returns token from session', async () => {
      const mockToken = 'session-jwt-token'
      // Return a user object with getSession method
      mockFns.getCurrentUser!.mockReturnValue({
        getSession: (callback: (err: null, session: unknown) => void) => {
          callback(null, {
            getIdToken: () => ({
              getJwtToken: () => mockToken,
            }),
          })
        },
      })

      const result = await getIdToken()

      expect(result).toBe(mockToken)
    })

    it('rejects when getSession fails', async () => {
      mockFns.getCurrentUser!.mockReturnValue({
        getSession: (callback: (err: Error, session: null) => void) => {
          callback(new Error('Session expired'), null)
        },
      })

      await expect(getIdToken()).rejects.toThrow('Session expired')
    })

    it('returns null when session is null', async () => {
      mockFns.getCurrentUser!.mockReturnValue({
        getSession: (callback: (err: null, session: null) => void) => {
          callback(null, null)
        },
      })

      const result = await getIdToken()

      expect(result).toBeNull()
    })
  })

  describe('signOut', () => {
    it('calls signOut on current user', () => {
      const userSignOut = vi.fn()
      mockFns.getCurrentUser!.mockReturnValue({
        signOut: userSignOut,
      })

      signOut()

      expect(userSignOut).toHaveBeenCalled()
    })

    it('does nothing when no current user', () => {
      mockFns.getCurrentUser!.mockReturnValue(null)

      // Should not throw
      expect(() => signOut()).not.toThrow()
    })
  })
})
