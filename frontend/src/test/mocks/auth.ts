import { vi } from 'vitest'

interface AuthMockConfig {
  signInResult?: string | Error
  signUpResult?: void | Error
  getIdTokenResult?: string | null | Error
  getCurrentUserResult?: { username: string } | null
}

// Default mock implementations
const defaultConfig: AuthMockConfig = {
  signInResult: 'mock-id-token-123',
  signUpResult: undefined,
  getIdTokenResult: 'mock-id-token-123',
  getCurrentUserResult: { username: 'test@example.com' },
}

export function createAuthMock(config: AuthMockConfig = {}) {
  const mergedConfig = { ...defaultConfig, ...config }

  const signIn = vi.fn().mockImplementation(async () => {
    if (mergedConfig.signInResult instanceof Error) {
      throw mergedConfig.signInResult
    }
    return mergedConfig.signInResult
  })

  const signUp = vi.fn().mockImplementation(async () => {
    if (mergedConfig.signUpResult instanceof Error) {
      throw mergedConfig.signUpResult
    }
    return mergedConfig.signUpResult
  })

  const getIdToken = vi.fn().mockImplementation(async () => {
    if (mergedConfig.getIdTokenResult instanceof Error) {
      throw mergedConfig.getIdTokenResult
    }
    return mergedConfig.getIdTokenResult
  })

  const getCurrentUser = vi.fn().mockReturnValue(mergedConfig.getCurrentUserResult)

  const signOut = vi.fn()

  return {
    signIn,
    signUp,
    getIdToken,
    getCurrentUser,
    signOut,
    // Helper to reset all mocks
    reset: () => {
      signIn.mockClear()
      signUp.mockClear()
      getIdToken.mockClear()
      getCurrentUser.mockClear()
      signOut.mockClear()
    },
  }
}

// Common error scenarios
export const authErrors = {
  invalidCredentials: new Error('Incorrect username or password.'),
  userNotFound: new Error('User does not exist.'),
  userNotConfirmed: new Error('User is not confirmed.'),
  networkError: new Error('Network error'),
  tooManyRequests: new Error('Too many requests. Please try again later.'),
  passwordRequirements: new Error('Password does not conform to policy'),
  usernameExists: new Error('User already exists'),
}

