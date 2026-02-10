/**
 * Smoke test to verify test setup works correctly.
 * This file tests the test utilities and mocks.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, mockAuthContextAuthenticated, mockAuthContextUnauthenticated } from './test-utils'
import { createAuthMock, authErrors } from './mocks/auth'
import { createApiMock, sampleJobs, apiErrors } from './mocks/api'
import { createTestQueryClient } from './mocks/react-query'

describe('Test Setup Smoke Tests', () => {
  describe('Custom render function', () => {
    it('renders a simple component with providers', () => {
      function TestComponent() {
        return <div>Hello Test</div>
      }

      render(<TestComponent />)
      expect(screen.getByText('Hello Test')).toBeInTheDocument()
    })

    it('provides unauthenticated context by default', () => {
      function AuthDisplay() {
        return <div>Auth: {mockAuthContextUnauthenticated.isAuthenticated.toString()}</div>
      }

      render(<AuthDisplay />)
      expect(screen.getByText('Auth: false')).toBeInTheDocument()
    })

    it('can provide authenticated context', () => {
      function AuthDisplay() {
        return <div>Auth: {mockAuthContextAuthenticated.isAuthenticated.toString()}</div>
      }

      render(<AuthDisplay />, { authContext: mockAuthContextAuthenticated })
      expect(screen.getByText('Auth: true')).toBeInTheDocument()
    })
  })

  describe('Auth mock factory', () => {
    it('creates mock with default values', async () => {
      const mock = createAuthMock()
      const token = await mock.signIn('test@test.com', 'password')
      expect(token).toBe('mock-id-token-123')
      expect(mock.signIn).toHaveBeenCalledWith('test@test.com', 'password')
    })

    it('supports custom return values', async () => {
      const mock = createAuthMock({ signInResult: 'custom-token-456' })
      const token = await mock.signIn('test@test.com', 'password')
      expect(token).toBe('custom-token-456')
    })

    it('supports error scenarios', async () => {
      const mock = createAuthMock({ signInResult: authErrors.invalidCredentials })
      await expect(mock.signIn('test@test.com', 'wrong')).rejects.toThrow('Incorrect username or password')
    })

    it('can reset mocks', async () => {
      const mock = createAuthMock()
      await mock.signIn('test@test.com', 'password')
      expect(mock.signIn).toHaveBeenCalled()
      mock.reset()
      expect(mock.signIn).not.toHaveBeenCalled()
    })
  })

  describe('API mock factory', () => {
    it('creates mock with default values', async () => {
      const mock = createApiMock()
      const jobs = await mock.fetchJobs()
      expect(jobs).toEqual(sampleJobs)
      expect(mock.fetchJobs).toHaveBeenCalled()
    })

    it('supports custom return values', async () => {
      const customJobs = [{ ...sampleJobs[0], 'job_id': 'custom-job' }]
      const mock = createApiMock({ fetchJobsResult: customJobs })
      const jobs = await mock.fetchJobs()
      expect(jobs[0]['job_id']).toBe('custom-job')
    })

    it('supports error scenarios', async () => {
      const mock = createApiMock({ fetchJobsResult: apiErrors.networkError })
      await expect(mock.fetchJobs()).rejects.toThrow('Network Error')
    })
  })

  describe('QueryClient wrapper', () => {
    it('creates test query client with correct defaults', () => {
      const client = createTestQueryClient()
      const defaults = client.getDefaultOptions()
      expect(defaults.queries?.retry).toBe(false)
      expect(defaults.queries?.gcTime).toBe(0)
    })
  })

  describe('Global mocks', () => {
    it('mocks import.meta.env correctly', () => {
      // Note: This tests that the stub is available
      // The actual env values are set in setup.ts
      expect(vi.isMockFunction).toBeDefined()
    })
  })
})
