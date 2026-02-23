import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, createTestQueryClient } from '../test/test-utils'
import { mockAuthContextAuthenticated } from '../test/test-utils'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../contexts/AuthContext'
import { ToastProvider } from '../contexts/ToastContext'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchUserTemplates: vi.fn(),
    searchMarketplaceTemplates: vi.fn(),
    forkTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    fetchTemplate: vi.fn(),
  }
})

import {
  fetchUserTemplates,
  searchMarketplaceTemplates,
  forkTemplate,
} from '../services/api'
import Templates from './Templates'

function renderWithToast(ui: React.ReactElement) {
  const client = createTestQueryClient()
  return render(ui, {
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
}

const myTemplates = [
  {
    template_id: 'tmpl-1',
    version: 1,
    name: 'My Template',
    description: 'My own template',
    user_id: 'user-123',
    is_public: false,
    is_owner: true,
    created_at: '2026-02-20T00:00:00Z',
    steps: [{ id: 'q1', prompt: 'Hello', model_tier: 'tier-1' }],
    schema_requirements: ['field1'],
  },
]

const marketplaceResults = {
  templates: [
    {
      template_id: 'tmpl-pub-1',
      name: 'Public Template',
      description: 'A public template',
      user_id: 'other-user',
      version: 1,
      schema_requirements: ['author.name'],
      step_count: 2,
      created_at: '2026-02-19T00:00:00Z',
    },
  ],
  count: 1,
  total: 1,
}

describe('Templates', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders My Templates tab with user templates', async () => {
    vi.mocked(fetchUserTemplates).mockResolvedValueOnce(myTemplates)

    renderWithToast(<Templates />)

    await waitFor(() => {
      expect(screen.getByText('My Template')).toBeInTheDocument()
    })

    expect(screen.getByText('Edit')).toBeInTheDocument()
  })

  it('switches to Marketplace tab', async () => {
    vi.mocked(fetchUserTemplates).mockResolvedValueOnce(myTemplates)
    vi.mocked(searchMarketplaceTemplates).mockResolvedValueOnce(marketplaceResults)

    renderWithToast(<Templates />)

    await waitFor(() => {
      expect(screen.getByText('My Template')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Marketplace'))

    await waitFor(() => {
      expect(screen.getByText('Public Template')).toBeInTheDocument()
    })
  })

  it('search input triggers API call', async () => {
    vi.mocked(fetchUserTemplates).mockResolvedValue(myTemplates)
    vi.mocked(searchMarketplaceTemplates).mockResolvedValue(marketplaceResults)

    renderWithToast(<Templates />)

    // Switch to marketplace
    fireEvent.click(screen.getByText('Marketplace'))

    await waitFor(() => {
      expect(searchMarketplaceTemplates).toHaveBeenCalled()
    })

    // Type in search
    const searchInput = screen.getByPlaceholderText('Search templates...')
    fireEvent.change(searchInput, { target: { value: 'poetry' } })

    await waitFor(() => {
      expect(searchMarketplaceTemplates).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'poetry' })
      )
    })
  })

  it('fork success shows toast and switches tab', async () => {
    vi.mocked(fetchUserTemplates).mockResolvedValue(myTemplates)
    vi.mocked(searchMarketplaceTemplates).mockResolvedValue(marketplaceResults)
    vi.mocked(forkTemplate).mockResolvedValueOnce({ template_id: 'new-tmpl' })

    renderWithToast(<Templates />)

    // Switch to marketplace
    fireEvent.click(screen.getByText('Marketplace'))

    await waitFor(() => {
      expect(screen.getByText('Public Template')).toBeInTheDocument()
    })

    // Click fork
    fireEvent.click(screen.getByText('Fork'))

    await waitFor(() => {
      expect(forkTemplate).toHaveBeenCalledWith('tmpl-pub-1')
    })
  })
})
