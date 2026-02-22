import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import VersionList from './VersionList'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  fetchTemplateVersions: vi.fn(),
}))

const mockFetchVersions = vi.mocked(api.fetchTemplateVersions)

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
}

function renderVersionList(props = {}) {
  const defaultProps = {
    templateId: 'tmpl-123',
    currentVersion: 2,
    onSelectVersion: vi.fn(),
    ...props,
  }

  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <VersionList {...defaultProps} />
    </QueryClientProvider>
  )
}

describe('VersionList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders version list with correct items', async () => {
    mockFetchVersions.mockResolvedValueOnce([
      { version: 3, name: 'v3 name', description: '', created_at: '2025-01-03T00:00:00' },
      { version: 2, name: 'v2 name', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: 'v1 name', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList()

    await waitFor(() => {
      expect(screen.getByText('v3')).toBeInTheDocument()
      expect(screen.getByText('v2')).toBeInTheDocument()
      expect(screen.getByText('v1')).toBeInTheDocument()
    })
  })

  it('highlights current version', async () => {
    mockFetchVersions.mockResolvedValueOnce([
      { version: 2, name: '', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: '', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList({ currentVersion: 2 })

    await waitFor(() => {
      expect(screen.getByText('current')).toBeInTheDocument()
    })
  })

  it('calls onSelectVersion when version clicked', async () => {
    const user = userEvent.setup()
    const onSelectVersion = vi.fn()

    mockFetchVersions.mockResolvedValueOnce([
      { version: 2, name: '', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: '', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList({ currentVersion: 2, onSelectVersion })

    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument()
    })

    // Click on version 1 entry
    await user.click(screen.getByText('v1'))

    expect(onSelectVersion).toHaveBeenCalledWith(1)
  })

  it('shows loading state', () => {
    mockFetchVersions.mockReturnValue(new Promise(() => {})) // never resolves

    renderVersionList()

    expect(screen.getByText('Loading versions...')).toBeInTheDocument()
  })

  it('shows error state', async () => {
    mockFetchVersions.mockRejectedValueOnce(new Error('Network error'))

    renderVersionList()

    await waitFor(() => {
      expect(screen.getByText(/Failed to load versions/)).toBeInTheDocument()
    })
  })

  it('shows Compare button for non-current versions when onCompare is provided', async () => {
    mockFetchVersions.mockResolvedValueOnce([
      { version: 2, name: '', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: '', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList({ currentVersion: 2, onCompare: vi.fn() })

    await waitFor(() => {
      // Compare button shows only for non-current version
      expect(screen.getByText('Compare')).toBeInTheDocument()
    })

    // Only 1 Compare button (version 1 only, not current version 2)
    expect(screen.getAllByText('Compare')).toHaveLength(1)
  })

  it('calls onCompare when Compare button is clicked', async () => {
    const user = userEvent.setup()
    const onCompare = vi.fn()

    mockFetchVersions.mockResolvedValueOnce([
      { version: 2, name: '', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: '', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList({ currentVersion: 2, onCompare })

    await waitFor(() => {
      expect(screen.getByText('Compare')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Compare'))

    expect(onCompare).toHaveBeenCalledWith(1)
  })

  it('does not show Compare buttons when onCompare is not provided', async () => {
    mockFetchVersions.mockResolvedValueOnce([
      { version: 2, name: '', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: '', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    renderVersionList({ currentVersion: 2 })

    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument()
    })

    expect(screen.queryByText('Compare')).not.toBeInTheDocument()
  })
})
