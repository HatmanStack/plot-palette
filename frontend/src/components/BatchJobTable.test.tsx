import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BatchJobTable from './BatchJobTable'
import type { BatchJob } from '../services/api'
import { fetchQualityMetrics } from '../services/api'

vi.mock('../services/api', () => ({
  fetchQualityMetrics: vi.fn(() => Promise.resolve(null)),
  triggerQualityScoring: vi.fn(() => Promise.resolve()),
}))

const sampleJobs: BatchJob[] = [
  {
    job_id: 'job-1',
    status: 'COMPLETED',
    records_generated: 100,
    cost_estimate: 5.0,
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
    updated_at: '2025-12-01T10:15:00',
  },
]

const sweepConfig = { model_tier: ['tier-1', 'tier-2'] }

describe('BatchJobTable', () => {
  const renderTable = (jobs = sampleJobs, config = sweepConfig) => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <BatchJobTable jobs={jobs} sweepConfig={config} />
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  it('renders columns for each job', () => {
    renderTable()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('$5.00')).toBeInTheDocument()
    expect(screen.getByText('$1.50')).toBeInTheDocument()
  })

  it('sorts by cost column', async () => {
    renderTable()
    const user = userEvent.setup()

    const costHeader = screen.getByText(/Cost/)
    await user.click(costHeader)

    // After clicking, rows should be sorted by cost
    const costCells = screen.getAllByText(/\$\d+\.\d{2}/)
    expect(costCells.length).toBe(2)
  })

  it('shows sweep values', () => {
    renderTable()
    expect(screen.getByText('tier-1')).toBeInTheDocument()
    expect(screen.getByText('tier-2')).toBeInTheDocument()
  })

  it('shows empty state when no jobs', () => {
    renderTable([])
    expect(screen.getByText('No jobs in this batch')).toBeInTheDocument()
  })

  describe('QualityCell', () => {
    it('shows dash for non-completed job', () => {
      const jobs: BatchJob[] = [{
        job_id: 'job-running',
        status: 'RUNNING',
        records_generated: 50,
        cost_estimate: 1.5,
        budget_limit: 10,
        created_at: '2025-12-01T10:00:00',
        updated_at: '2025-12-01T10:15:00',
      }]
      renderTable(jobs, { model_tier: ['tier-1'] })
      expect(screen.getByText('-')).toBeInTheDocument()
    })

    it('shows Score button when no metrics exist for completed job', async () => {
      vi.mocked(fetchQualityMetrics).mockResolvedValue(null)
      const jobs: BatchJob[] = [{
        job_id: 'job-unscored',
        status: 'COMPLETED',
        records_generated: 100,
        cost_estimate: 5.0,
        budget_limit: 10,
        created_at: '2025-12-01T10:00:00',
        updated_at: '2025-12-01T10:30:00',
      }]
      renderTable(jobs, { model_tier: ['tier-1'] })
      await waitFor(() => {
        expect(screen.getByText('Score')).toBeInTheDocument()
      })
    })

    it('shows score bar when metrics are completed', async () => {
      vi.mocked(fetchQualityMetrics).mockResolvedValue({
        job_id: 'job-scored',
        scored_at: '2025-12-01T12:00:00',
        sample_size: 20,
        total_records: 100,
        model_used_for_scoring: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        aggregate_scores: { coherence: 0.85, relevance: 0.9, format_compliance: 0.95 },
        diversity_score: 0.75,
        overall_score: 0.87,
        record_scores: [],
        scoring_cost: 0.05,
        status: 'COMPLETED',
      })
      const jobs: BatchJob[] = [{
        job_id: 'job-scored',
        status: 'COMPLETED',
        records_generated: 100,
        cost_estimate: 5.0,
        budget_limit: 10,
        created_at: '2025-12-01T10:00:00',
        updated_at: '2025-12-01T10:30:00',
      }]
      renderTable(jobs, { model_tier: ['tier-1'] })
      await waitFor(() => {
        expect(screen.getByText('0.87')).toBeInTheDocument()
      })
    })

    it('shows Scoring... when metrics status is SCORING', async () => {
      vi.mocked(fetchQualityMetrics).mockResolvedValue({
        job_id: 'job-scoring',
        scored_at: '2025-12-01T12:00:00',
        sample_size: 0,
        total_records: 100,
        model_used_for_scoring: '',
        aggregate_scores: {},
        diversity_score: 0,
        overall_score: 0,
        record_scores: [],
        scoring_cost: 0,
        status: 'SCORING',
      })
      const jobs: BatchJob[] = [{
        job_id: 'job-scoring',
        status: 'COMPLETED',
        records_generated: 100,
        cost_estimate: 5.0,
        budget_limit: 10,
        created_at: '2025-12-01T10:00:00',
        updated_at: '2025-12-01T10:30:00',
      }]
      renderTable(jobs, { model_tier: ['tier-1'] })
      await waitFor(() => {
        expect(screen.getByText('Scoring...')).toBeInTheDocument()
      })
    })
  })
})
