/**
 * Tests for auth token error handling in getAuthHeaders.
 *
 * Verifies that auth token fetch errors propagate instead of
 * being silently swallowed (health-audit HIGH-1).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock auth module
vi.mock('../../services/auth', () => ({
  getIdToken: vi.fn(),
}))

import * as authService from '../../services/auth'
import { getAuthHeaders } from '../../services/api'

describe('Auth token error handling - getAuthHeaders', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('propagates auth token error instead of silently returning empty object', async () => {
    const mockGetIdToken = vi.mocked(authService.getIdToken)
    mockGetIdToken.mockRejectedValue(new Error('Token refresh failed'))

    // After the fix, getAuthHeaders should propagate the error
    // instead of catching it and returning {}
    await expect(getAuthHeaders()).rejects.toThrow('Token refresh failed')
  })

  it('returns Authorization header when token is available', async () => {
    const mockGetIdToken = vi.mocked(authService.getIdToken)
    mockGetIdToken.mockResolvedValue('valid-token')

    const headers = await getAuthHeaders()
    expect(headers).toEqual({ Authorization: 'Bearer valid-token' })
  })

  it('returns empty object when no user is logged in (null token)', async () => {
    const mockGetIdToken = vi.mocked(authService.getIdToken)
    mockGetIdToken.mockResolvedValue(null)

    const headers = await getAuthHeaders()
    expect(headers).toEqual({})
  })
})
