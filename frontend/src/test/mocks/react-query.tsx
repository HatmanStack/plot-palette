import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

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

interface QueryClientWrapperProps {
  children: ReactNode
  client?: QueryClient
}

// Wrapper component for tests that need QueryClient
export function QueryClientWrapper({ children, client }: QueryClientWrapperProps) {
  const queryClient = client ?? createTestQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

// HOC for wrapping components in QueryClientProvider
export function withQueryClient<P extends object>(
  Component: React.ComponentType<P>,
  client?: QueryClient
) {
  return function WrappedComponent(props: P) {
    return (
      <QueryClientWrapper client={client}>
        <Component {...props} />
      </QueryClientWrapper>
    )
  }
}
