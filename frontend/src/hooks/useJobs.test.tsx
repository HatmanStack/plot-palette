import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useJobs } from './useJobs'
import * as api from '../services/api'
import { createTestQueryClient } from '../test/test-utils'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// Mock the API module
vi.mock('../services/api', () => ({
  fetchJobs: vi.fn(),
}))

const mockFetchJobs = vi.mocked(api.fetchJobs)

describe('useJobs', () => {
  let queryClient: ReturnType<typeof createTestQueryClient>

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = createTestQueryClient()
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )

  it('fetches jobs successfully', async () => {
    const mockJobs: api.Job[] = [
      {
        'job-id': 'job-123',
        'user-id': 'user-456',
        status: 'COMPLETED',
        'created-at': '2024-01-01T00:00:00Z',
        'updated-at': '2024-01-01T01:00:00Z',
        'template-id': 'template-789',
        'budget-limit': 100,
        'num-records': 1000,
        'records-generated': 1000,
        'tokens-used': 50000,
        'cost-estimate': 0.5,
      },
    ]

    mockFetchJobs.mockResolvedValueOnce(mockJobs)

    const { result } = renderHook(() => useJobs(), { wrapper })

    // Initially loading
    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual(mockJobs)
    expect(result.current.isError).toBe(false)
    expect(mockFetchJobs).toHaveBeenCalledTimes(1)
  })

  it('handles error when fetching fails', async () => {
    const error = new Error('Network error')
    mockFetchJobs.mockRejectedValueOnce(error)

    const { result } = renderHook(() => useJobs(), { wrapper })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
    expect(result.current.data).toBeUndefined()
  })

  it('returns empty array when no jobs exist', async () => {
    mockFetchJobs.mockResolvedValueOnce([])

    const { result } = renderHook(() => useJobs(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual([])
    expect(result.current.isError).toBe(false)
  })

  it('returns multiple jobs correctly', async () => {
    const mockJobs: api.Job[] = [
      {
        'job-id': 'job-1',
        'user-id': 'user-1',
        status: 'RUNNING',
        'created-at': '2024-01-01T00:00:00Z',
        'updated-at': '2024-01-01T01:00:00Z',
        'template-id': 'template-1',
        'budget-limit': 50,
        'num-records': 500,
        'records-generated': 250,
        'tokens-used': 25000,
        'cost-estimate': 0.25,
      },
      {
        'job-id': 'job-2',
        'user-id': 'user-1',
        status: 'QUEUED',
        'created-at': '2024-01-02T00:00:00Z',
        'updated-at': '2024-01-02T00:00:00Z',
        'template-id': 'template-2',
        'budget-limit': 100,
        'num-records': 1000,
        'records-generated': 0,
        'tokens-used': 0,
        'cost-estimate': 0,
      },
    ]

    mockFetchJobs.mockResolvedValueOnce(mockJobs)

    const { result } = renderHook(() => useJobs(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toHaveLength(2)
    expect(result.current.data?.[0]['job-id']).toBe('job-1')
    expect(result.current.data?.[1]['job-id']).toBe('job-2')
  })
})
