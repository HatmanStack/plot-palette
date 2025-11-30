import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useJobPolling } from './useJobPolling'
import * as api from '../services/api'
import { createTestQueryClient } from '../test/test-utils'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

// Mock the API module
vi.mock('../services/api', () => ({
  fetchJobDetails: vi.fn(),
}))

const mockFetchJobDetails = vi.mocked(api.fetchJobDetails)

describe('useJobPolling', () => {
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

  const createMockJob = (overrides: Partial<api.Job> = {}): api.Job => ({
    'job-id': 'job-123',
    'user-id': 'user-456',
    status: 'RUNNING',
    'created-at': '2024-01-01T00:00:00Z',
    'updated-at': '2024-01-01T01:00:00Z',
    'template-id': 'template-789',
    'budget-limit': 100,
    'num-records': 1000,
    'records-generated': 500,
    'tokens-used': 25000,
    'cost-estimate': 0.25,
    ...overrides,
  })

  it('fetches job details with provided jobId', async () => {
    const mockJob = createMockJob()
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockFetchJobDetails).toHaveBeenCalledWith('job-123')
    expect(result.current.data).toEqual(mockJob)
  })

  it('returns job with RUNNING status', async () => {
    const mockJob = createMockJob({ status: 'RUNNING' })
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.data?.status).toBe('RUNNING')
    })
  })

  it('returns job with QUEUED status', async () => {
    const mockJob = createMockJob({ status: 'QUEUED' })
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.data?.status).toBe('QUEUED')
    })
  })

  it('returns job with COMPLETED status', async () => {
    const mockJob = createMockJob({
      status: 'COMPLETED',
      'records-generated': 1000,
    })
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.data?.status).toBe('COMPLETED')
    })

    expect(result.current.data?.['records-generated']).toBe(1000)
  })

  it('returns job with FAILED status', async () => {
    const mockJob = createMockJob({ status: 'FAILED' })
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.data?.status).toBe('FAILED')
    })
  })

  it('returns job with CANCELLED status', async () => {
    const mockJob = createMockJob({ status: 'CANCELLED' })
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.data?.status).toBe('CANCELLED')
    })
  })

  it('handles fetch error', async () => {
    mockFetchJobDetails.mockRejectedValueOnce(new Error('Not found'))

    const { result } = renderHook(() => useJobPolling('job-123'), { wrapper })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
  })

  it('uses correct queryKey with jobId', async () => {
    const mockJob = createMockJob()
    mockFetchJobDetails.mockResolvedValueOnce(mockJob)

    renderHook(() => useJobPolling('unique-job-id'), { wrapper })

    await waitFor(() => {
      expect(mockFetchJobDetails).toHaveBeenCalledWith('unique-job-id')
    })
  })
})
