import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { AuthContext } from '../contexts/AuthContext'
import type { AuthContextType } from '../contexts/AuthContext'
import { useJobStream } from './useJobStream'

// Mock EventSource
let mockEventSourceInstance: MockEventSource | null = null

class MockEventSource {
  url: string
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readyState = 1 // OPEN
  close = vi.fn()
  private listeners: Record<string, ((event: MessageEvent) => void)[]> = {}

  constructor(url: string) {
    this.url = url
    mockEventSourceInstance = this
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (!this.listeners[type]) {
      this.listeners[type] = []
    }
    this.listeners[type].push(listener)
  }

  removeEventListener() {
    // no-op for tests
  }

  // Test helpers
  simulateOpen() {
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent)
  }

  simulateEvent(type: string, data: string) {
    const handlers = this.listeners[type] || []
    for (const handler of handlers) {
      handler({ data } as MessageEvent)
    }
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }
}

vi.stubGlobal('EventSource', MockEventSource)

const mockAuth: AuthContextType = {
  isAuthenticated: true,
  idToken: 'mock-token-123',
  login: async () => {},
  signup: async () => {},
  logout: () => {},
  loading: false,
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(AuthContext.Provider, { value: mockAuth }, children),
    )
  }
}

describe('useJobStream', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    mockEventSourceInstance = null
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    })
    // Seed initial job data so useJobStream doesn't skip terminal check
    queryClient.setQueryData(['job', 'job-123'], {
      job_id: 'job-123',
      status: 'RUNNING',
      records_generated: 50,
      tokens_used: 1000,
      cost_estimate: 1.0,
      budget_limit: 10.0,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('creates EventSource with correct URL including token', () => {
    renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    expect(mockEventSourceInstance).not.toBeNull()
    expect(mockEventSourceInstance!.url).toContain('/jobs/job-123/stream')
    expect(mockEventSourceInstance!.url).toContain('token=mock-token-123')
  })

  it('updates React Query cache on message', () => {
    renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    act(() => {
      mockEventSourceInstance!.simulateMessage(
        JSON.stringify({
          job_id: 'job-123',
          status: 'RUNNING',
          records_generated: 200,
          cost_estimate: 2.5,
        }),
      )
    })

    const cached = queryClient.getQueryData(['job', 'job-123']) as Record<string, unknown>
    expect(cached.records_generated).toBe(200)
    expect(cached.cost_estimate).toBe(2.5)
  })

  it('closes EventSource on terminal status', () => {
    renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    act(() => {
      mockEventSourceInstance!.simulateMessage(
        JSON.stringify({
          job_id: 'job-123',
          status: 'COMPLETED',
          records_generated: 500,
        }),
      )
    })

    expect(mockEventSourceInstance!.close).toHaveBeenCalled()
  })

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    const es = mockEventSourceInstance!
    unmount()

    expect(es.close).toHaveBeenCalled()
  })

  it('sets isConnected to true when open', () => {
    const { result } = renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    act(() => {
      mockEventSourceInstance!.simulateOpen()
    })

    expect(result.current.isConnected).toBe(true)
  })

  it('sets error on EventSource error', () => {
    const { result } = renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(queryClient),
    })

    act(() => {
      mockEventSourceInstance!.simulateError()
    })

    expect(result.current.error).not.toBeNull()
    expect(result.current.isConnected).toBe(false)
  })
})
