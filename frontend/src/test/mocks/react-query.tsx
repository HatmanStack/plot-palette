import { QueryClient } from '@tanstack/react-query'

// Create a test-optimized QueryClient
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Disable retries in tests
        retry: false,
        // No garbage collection time between tests
        gcTime: 0,
        // Always consider data stale in tests
        staleTime: 0,
        // Disable refetching on window focus
        refetchOnWindowFocus: false,
      },
      mutations: {
        // Disable retries in tests
        retry: false,
      },
    },
  })
}
