/**
 * Tests for network error handling in the fetch wrapper.
 *
 * Verifies that TypeError (network), AbortError (timeout), and
 * other fetch-level errors are caught and wrapped with descriptive messages.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock auth module
vi.mock('../../services/auth', () => ({
  getIdToken: vi.fn().mockResolvedValue('test-token'),
}))

// The api module reads BASE_URL = import.meta.env.VITE_API_ENDPOINT at import
// time. The setup.ts stubs import.meta.env, but we need to ensure the api module
// is freshly imported after the stub is applied. We use dynamic import in each
// test to guarantee the right module state.

describe('Network error handling in fetch wrapper', () => {
  let originalFetch: typeof globalThis.fetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('catches TypeError (network failure) and returns descriptive message', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))

    // Import after mocking fetch
    const { fetchJobs } = await import('../../services/api')
    await expect(fetchJobs()).rejects.toThrow(
      'Network error: unable to reach the server. Check your connection.'
    )
  })

  it('catches AbortError (timeout) and returns timeout message', async () => {
    const abortError = new DOMException('The operation was aborted', 'AbortError')
    globalThis.fetch = vi.fn().mockRejectedValue(abortError)

    const { fetchJobs } = await import('../../services/api')
    await expect(fetchJobs()).rejects.toThrow('Request timed out. Please try again.')
  })

  it('catches unknown errors and wraps with network error prefix', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Something unexpected'))

    const { fetchJobs } = await import('../../services/api')
    await expect(fetchJobs()).rejects.toThrow('Network error: Something unexpected')
  })

  it('still handles server errors (non-ok response) correctly', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ message: 'Internal server error' }),
    })

    const { fetchJobs } = await import('../../services/api')
    await expect(fetchJobs()).rejects.toThrow('Internal server error')
  })
})
