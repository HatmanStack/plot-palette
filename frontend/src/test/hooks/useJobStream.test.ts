import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createElement } from 'react'

// Mock useAuth
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    idToken: 'mock-token',
  }),
}))

// Track the latest EventSource instance
interface MockES {
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  onerror: ((event: Event) => void) | null
  addEventListener: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  removeEventListener: ReturnType<typeof vi.fn>
}
let latestES: MockES | null = null

vi.stubGlobal(
  'EventSource',
  class {
    onopen: ((event: Event) => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null
    onerror: ((event: Event) => void) | null = null
    addEventListener = vi.fn()
    close = vi.fn()
    removeEventListener = vi.fn()
    constructor() {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      latestES = this
    }
  }
)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
  // Seed the query cache with a job so the hook doesn't skip
  queryClient.setQueryData(['job', 'job-123'], {
    job_id: 'job-123',
    status: 'RUNNING',
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

describe('useJobStream parse error logging', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    latestES = null
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('logs parse errors on invalid SSE message data', async () => {
    const { useJobStream } = await import('../../hooks/useJobStream')

    renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(),
    })

    expect(latestES).not.toBeNull()

    // Simulate receiving invalid JSON via onmessage
    const onmessage = latestES!.onmessage
    expect(onmessage).toBeDefined()

    act(() => {
      onmessage!(new MessageEvent('message', { data: 'not valid json{{{' }))
    })

    // console.error should have been called with structured data
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      '[useJobStream] Failed to parse SSE message:',
      expect.objectContaining({
        jobId: 'job-123',
        rawData: 'not valid json{{{',
        error: expect.any(String),
      })
    )
  })

  it('does not crash on parse errors', async () => {
    const { useJobStream } = await import('../../hooks/useJobStream')

    const { result } = renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(),
    })

    const onmessage = latestES!.onmessage

    // Send invalid JSON -- should not throw
    act(() => {
      onmessage!(new MessageEvent('message', { data: '<<<invalid>>>' }))
    })

    // Hook should still be functional
    expect(result.current.error).toBeNull()
  })

  it('logs parse errors on invalid complete event data', async () => {
    const { useJobStream } = await import('../../hooks/useJobStream')

    renderHook(() => useJobStream('job-123'), {
      wrapper: createWrapper(),
    })

    // Get the 'complete' event listener
    const completeCall = latestES!.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'complete'
    )
    expect(completeCall).toBeDefined()

    const completeListener = completeCall![1] as (
      event: MessageEvent
    ) => void

    act(() => {
      completeListener(new MessageEvent('complete', { data: 'bad json' }))
    })

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      '[useJobStream] Failed to parse SSE complete event:',
      expect.objectContaining({
        jobId: 'job-123',
        rawData: 'bad json',
      })
    )
  })
})
