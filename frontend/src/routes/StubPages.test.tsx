import { describe, it, expect, vi } from 'vitest'
import { render, screen, createTestQueryClient, mockAuthContextAuthenticated } from '../test/test-utils'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../contexts/AuthContext'
import { ToastProvider } from '../contexts/ToastContext'
import Jobs from './Jobs'
import Templates from './Templates'
import Settings from './Settings'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchUserTemplates: vi.fn().mockResolvedValue([]),
    searchMarketplaceTemplates: vi.fn().mockResolvedValue({ templates: [], count: 0, total: 0 }),
  }
})

describe('Jobs stub page', () => {
  it('renders heading', () => {
    render(<Jobs />)
    expect(screen.getByText('Jobs')).toBeInTheDocument()
  })
})

describe('Templates page', () => {
  it('renders heading', () => {
    const client = createTestQueryClient()
    render(<Templates />, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>
          <AuthContext.Provider value={mockAuthContextAuthenticated}>
            <ToastProvider>
              <MemoryRouter initialEntries={['/templates']}>
                {children}
              </MemoryRouter>
            </ToastProvider>
          </AuthContext.Provider>
        </QueryClientProvider>
      ),
      withRouter: false,
    })
    expect(screen.getByText('Templates')).toBeInTheDocument()
  })
})

describe('Settings stub page', () => {
  it('renders heading', () => {
    render(<Settings />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })
})
