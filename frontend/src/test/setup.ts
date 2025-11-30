import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Clean up after each test
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// Mock import.meta.env
vi.stubGlobal('import.meta', {
  env: {
    VITE_API_ENDPOINT: 'http://localhost:3000',
    VITE_COGNITO_USER_POOL_ID: 'us-east-1_test123',
    VITE_COGNITO_CLIENT_ID: 'test-client-id',
    MODE: 'test',
  },
})

// Mock amazon-cognito-identity-js
vi.mock('amazon-cognito-identity-js', () => ({
  CognitoUserPool: vi.fn().mockImplementation(() => ({
    signUp: vi.fn(),
    getCurrentUser: vi.fn(() => null),
  })),
  CognitoUser: vi.fn().mockImplementation(() => ({
    authenticateUser: vi.fn(),
    signOut: vi.fn(),
    getSession: vi.fn(),
  })),
  AuthenticationDetails: vi.fn(),
  CognitoUserAttribute: vi.fn(),
}))

// Suppress console errors in tests unless explicitly needed
const originalError = console.error
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    // Filter out expected React warnings during tests
    if (typeof args[0] === 'string' && args[0].includes('Warning:')) {
      return
    }
    originalError.call(console, ...args)
  }
})

afterAll(() => {
  console.error = originalError
})
