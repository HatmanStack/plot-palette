import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import CostSummaryCards from './CostSummaryCards'

const mockSummary = {
  total_spend: 1234.56,
  job_count: 42,
  avg_cost_per_job: 29.39,
  avg_cost_per_record: 0.125,
  budget_efficiency: 0.65,
  most_expensive_job: 'job-123',
}

describe('CostSummaryCards', () => {
  it('renders all 4 summary cards with correct values', () => {
    render(<CostSummaryCards summary={mockSummary} />, { withRouter: false })

    expect(screen.getByText('Total Spend')).toBeInTheDocument()
    expect(screen.getByText('Jobs Run')).toBeInTheDocument()
    expect(screen.getByText('Avg Cost / Job')).toBeInTheDocument()
    expect(screen.getByText('Budget Efficiency')).toBeInTheDocument()
  })

  it('formats currency correctly', () => {
    render(<CostSummaryCards summary={mockSummary} />, { withRouter: false })

    expect(screen.getByText('$1,234.56')).toBeInTheDocument()
    expect(screen.getByText('$29.39')).toBeInTheDocument()
  })

  it('shows 0 values for empty data', () => {
    const emptySummary = {
      total_spend: 0,
      job_count: 0,
      avg_cost_per_job: 0,
      avg_cost_per_record: 0,
      budget_efficiency: 0,
      most_expensive_job: null,
    }

    render(<CostSummaryCards summary={emptySummary} />, { withRouter: false })

    // Multiple $0.00 values (Total Spend, Avg Cost/Job)
    const zeroDollars = screen.getAllByText('$0.00')
    expect(zeroDollars.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('0.0%')).toBeInTheDocument()
  })
})
