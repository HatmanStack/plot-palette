import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import CreateBatch from './CreateBatch'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  createBatch: vi.fn(),
  generateUploadUrl: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { put: vi.fn() },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockCreateBatch = vi.mocked(api.createBatch)

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

describe('CreateBatch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderCreateBatch = () => {
    return render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <CreateBatch />
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  it('renders all wizard steps', async () => {
    renderCreateBatch()
    const user = userEvent.setup()

    // Step 1 visible
    expect(screen.getByText('Select Template')).toBeInTheDocument()

    // Navigate through steps
    await user.click(screen.getByText('Next'))
    expect(screen.getByText('Upload Seed Data')).toBeInTheDocument()

    await user.click(screen.getByText('Next'))
    expect(screen.getByText('Base Configuration')).toBeInTheDocument()

    await user.click(screen.getByText('Next'))
    expect(screen.getByText('Configure Sweep')).toBeInTheDocument()

    await user.click(screen.getByText('Next'))
    expect(screen.getByText('Review & Create')).toBeInTheDocument()
  })

  it('model tier sweep shows 3 checkboxes', async () => {
    renderCreateBatch()
    const user = userEvent.setup()

    // Navigate to step 4
    await user.click(screen.getByText('Next'))
    await user.click(screen.getByText('Next'))
    await user.click(screen.getByText('Next'))

    expect(screen.getByText('Tier 1 - Llama 3.1 8B (Cheap)')).toBeInTheDocument()
    expect(screen.getByText('Tier 2 - Llama 3.1 70B (Balanced)')).toBeInTheDocument()
    expect(screen.getByText('Tier 3 - Claude 3.5 Sonnet (Premium)')).toBeInTheDocument()
  })

  it('review step shows correct number of jobs', async () => {
    renderCreateBatch()
    const user = userEvent.setup()

    // Navigate to step 5
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByText('Next'))
    }

    // Default: 3 model tiers selected - check "Create 3 Jobs" button
    expect(screen.getByText(/Create 3 Jobs/)).toBeInTheDocument()
  })

  it('create calls API with correct config', async () => {
    mockCreateBatch.mockResolvedValueOnce({
      batch_id: 'batch-123',
      job_count: 3,
      job_ids: ['j1', 'j2', 'j3'],
    })

    renderCreateBatch()
    const user = userEvent.setup()

    // Fill step 1
    await user.type(screen.getByPlaceholderText(/A\/B test/), 'My Batch')
    await user.type(screen.getByPlaceholderText('Enter template ID'), 'tmpl-123')

    // Navigate to step 5
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByText('Next'))
    }

    await user.click(screen.getByText(/Create 3 Jobs/))

    expect(mockCreateBatch).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'My Batch',
        template_id: 'tmpl-123',
        sweep: { model_tier: ['tier-1', 'tier-2', 'tier-3'] },
      })
    )
  })
})
