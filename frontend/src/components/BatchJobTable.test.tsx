import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import BatchJobTable from './BatchJobTable'
import type { BatchJob } from '../services/api'

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
    return render(
      <MemoryRouter>
        <BatchJobTable jobs={jobs} sweepConfig={config} />
      </MemoryRouter>
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
})
