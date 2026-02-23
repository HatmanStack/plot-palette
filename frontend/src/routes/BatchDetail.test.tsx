import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import BatchDetail from './BatchDetail'
import { ToastProvider } from '../contexts/ToastContext'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  fetchBatchDetail: vi.fn(),
  deleteBatch: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockFetchBatchDetail = vi.mocked(api.fetchBatchDetail)
const mockDeleteBatch = vi.mocked(api.deleteBatch)

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

const sampleBatch: api.BatchDetail = {
  batch_id: 'batch-001',
  name: 'Model Comparison',
  status: 'RUNNING',
  total_jobs: 3,
  completed_jobs: 1,
  failed_jobs: 0,
  created_at: '2025-12-01T10:00:00',
  updated_at: '2025-12-01T11:00:00',
  total_cost: 5.25,
  template_id: 'tmpl-123',
  template_version: 1,
  sweep_config: { model_tier: ['tier-1', 'tier-2', 'tier-3'] },
  jobs: [
    {
      job_id: 'job-1',
      status: 'COMPLETED',
      records_generated: 100,
      cost_estimate: 3.0,
      budget_limit: 10,
      created_at: '2025-12-01T10:00:00',
      updated_at: '2025-12-01T10:30:00',
    },
    {
      job_id: 'job-2',
      status: 'RUNNING',
      records_generated: 50,
      cost_estimate: 1.5,
      budget_limit: 10,
      created_at: '2025-12-01T10:00:00',
      updated_at: '2025-12-01T10:30:00',
    },
    {
      job_id: 'job-3',
      status: 'QUEUED',
      records_generated: 0,
      cost_estimate: 0,
      budget_limit: 10,
      created_at: '2025-12-01T10:00:00',
      updated_at: '2025-12-01T10:00:00',
    },
  ],
}

describe('BatchDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderBatchDetail = () => {
    return render(
      <QueryClientProvider client={createTestQueryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/jobs/batches/batch-001']}>
            <Routes>
              <Route path="/jobs/batches/:batchId" element={<BatchDetail />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    )
  }

  it('renders batch header with progress', async () => {
    mockFetchBatchDetail.mockResolvedValueOnce(sampleBatch)
    renderBatchDetail()

    await waitFor(() => {
      expect(screen.getByText('Model Comparison')).toBeInTheDocument()
    })
    // The batch status badge + job table both show "RUNNING"
    expect(screen.getAllByText('RUNNING').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/1 of 3 jobs complete/)).toBeInTheDocument()
  })

  it('renders comparison table with all jobs', async () => {
    mockFetchBatchDetail.mockResolvedValueOnce(sampleBatch)
    renderBatchDetail()

    await waitFor(() => {
      expect(screen.getByText('Job Comparison')).toBeInTheDocument()
    })
    // Should have 3 "View" links
    const viewLinks = screen.getAllByText('View')
    expect(viewLinks).toHaveLength(3)
  })

  it('delete button calls deleteBatch', async () => {
    mockFetchBatchDetail.mockResolvedValueOnce(sampleBatch)
    mockDeleteBatch.mockResolvedValueOnce()

    renderBatchDetail()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Delete Batch')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Delete Batch'))
    // Confirm dialog appears
    await user.click(screen.getByText('Confirm Delete'))

    expect(mockDeleteBatch).toHaveBeenCalledWith('batch-001')
  })
})
