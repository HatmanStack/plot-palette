import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// Mock the api module
const mockFetchJobDetails = vi.fn()
vi.mock('../../services/api', () => ({
  fetchJobDetails: (...args: unknown[]) => mockFetchJobDetails(...args),
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

describe('useJobPolling', () => {
  beforeEach(() => {
    mockFetchJobDetails.mockReset()
  })

  it('should expose pollTimedOut as false initially', async () => {
    mockFetchJobDetails.mockResolvedValue({
      job_id: 'job-123',
      status: 'COMPLETED',
      records_generated: 100,
      num_records: 100,
    })

    const { useJobPolling } = await import('../../hooks/useJobPolling')

    const { result } = renderHook(() => useJobPolling('job-123', true), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.data).toBeDefined()
    })

    expect(result.current.pollTimedOut).toBe(false)
  })

  it('should not poll for terminal statuses', async () => {
    mockFetchJobDetails.mockResolvedValue({
      job_id: 'job-456',
      status: 'FAILED',
      records_generated: 50,
      num_records: 100,
    })

    const { useJobPolling } = await import('../../hooks/useJobPolling')

    const { result } = renderHook(() => useJobPolling('job-456', true), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.data).toBeDefined()
    })

    // Should fetch once but not keep polling for terminal status
    expect(mockFetchJobDetails).toHaveBeenCalledWith('job-456')
    expect(result.current.pollTimedOut).toBe(false)
  })

  it('should return query data alongside pollTimedOut', async () => {
    const jobData = {
      job_id: 'job-789',
      status: 'COMPLETED',
      records_generated: 100,
      num_records: 100,
    }
    mockFetchJobDetails.mockResolvedValue(jobData)

    const { useJobPolling } = await import('../../hooks/useJobPolling')

    const { result } = renderHook(() => useJobPolling('job-789', false), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.data).toBeDefined()
    })

    expect(result.current.data?.job_id).toBe('job-789')
    expect(result.current.pollTimedOut).toBe(false)
    // Standard react-query fields should be present
    expect(result.current.isLoading).toBeDefined()
    expect(result.current.isError).toBeDefined()
  })
})
