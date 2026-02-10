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
        'job_id': 'job-123',
        'user_id': 'user-456',
        status: 'COMPLETED',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T01:00:00Z',
        'template_id': 'template-789',
        'budget_limit': 100,
        'num_records': 1000,
        'records_generated': 1000,
        'tokens_used': 50000,
        'cost_estimate': 0.5,
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
        'job_id': 'job-1',
        'user_id': 'user-1',
        status: 'RUNNING',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T01:00:00Z',
        'template_id': 'template-1',
        'budget_limit': 50,
        'num_records': 500,
        'records_generated': 250,
        'tokens_used': 25000,
        'cost_estimate': 0.25,
      },
      {
        'job_id': 'job-2',
        'user_id': 'user-1',
        status: 'QUEUED',
        'created_at': '2024-01-02T00:00:00Z',
        'updated_at': '2024-01-02T00:00:00Z',
        'template_id': 'template-2',
        'budget_limit': 100,
        'num_records': 1000,
        'records_generated': 0,
        'tokens_used': 0,
        'cost_estimate': 0,
      },
    ]

    mockFetchJobs.mockResolvedValueOnce(mockJobs)

    const { result } = renderHook(() => useJobs(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toHaveLength(2)
    expect(result.current.data?.[0]['job_id']).toBe('job-1')
    expect(result.current.data?.[1]['job_id']).toBe('job-2')
  })
})
