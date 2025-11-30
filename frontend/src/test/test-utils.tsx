import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { ReactElement, ReactNode } from 'react'
import { AuthContext, AuthContextType } from '../contexts/AuthContext'

// Create a test QueryClient with sensible defaults for testing
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0, // No garbage collection time in tests
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

// Default mock auth context for unauthenticated users
export const mockAuthContextUnauthenticated: AuthContextType = {
  isAuthenticated: false,
  idToken: null,
  login: async () => {},
  signup: async () => {},
  logout: () => {},
  loading: false,
}

// Mock auth context for authenticated users
export const mockAuthContextAuthenticated: AuthContextType = {
  isAuthenticated: true,
  idToken: 'mock-id-token-123',
  login: async () => {},
  signup: async () => {},
  logout: () => {},
  loading: false,
}

// Options for customized rendering
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  authContext?: AuthContextType
  initialEntries?: string[]
  withRouter?: boolean
  queryClient?: QueryClient
}

// Create wrapper with all providers
function createWrapper({
  authContext = mockAuthContextUnauthenticated,
  initialEntries,
  withRouter = true,
  queryClient,
}: Omit<CustomRenderOptions, 'container' | 'baseElement'> = {}) {
  const client = queryClient ?? createTestQueryClient()

  return function Wrapper({ children }: { children: ReactNode }) {
    const content = (
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={authContext}>
          {children}
        </AuthContext.Provider>
      </QueryClientProvider>
    )

    if (!withRouter) {
      return content
    }

    // Use MemoryRouter if initialEntries provided, otherwise BrowserRouter
    if (initialEntries) {
      return <MemoryRouter initialEntries={initialEntries}>{content}</MemoryRouter>
    }

    return <BrowserRouter>{content}</BrowserRouter>
  }
}

// Custom render function with all providers
function customRender(
  ui: ReactElement,
  options: CustomRenderOptions = {}
) {
  const { authContext, initialEntries, withRouter, queryClient, ...renderOptions } = options

  return render(ui, {
    wrapper: createWrapper({ authContext, initialEntries, withRouter, queryClient }),
    ...renderOptions,
  })
}

// Re-export everything from testing-library
export * from '@testing-library/react'
export { customRender as render }
