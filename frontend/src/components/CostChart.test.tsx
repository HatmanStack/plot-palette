import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import CostChart from './CostChart'

const mockTimeSeries = [
  { date: '2026-02-18', bedrock: 5.0, fargate: 1.0, s3: 0.2, total: 6.2 },
  { date: '2026-02-19', bedrock: 8.0, fargate: 2.0, s3: 0.5, total: 10.5 },
  { date: '2026-02-20', bedrock: 3.0, fargate: 0.5, s3: 0.1, total: 3.6 },
]

describe('CostChart', () => {
  it('renders correct number of bars', () => {
    render(<CostChart timeSeries={mockTimeSeries} />, { withRouter: false })

    // Each bar has a date label
    expect(screen.getByText('02/18')).toBeInTheDocument()
    expect(screen.getByText('02/19')).toBeInTheDocument()
    expect(screen.getByText('02/20')).toBeInTheDocument()
  })

  it('renders chart title', () => {
    render(<CostChart timeSeries={mockTimeSeries} />, { withRouter: false })
    expect(screen.getByText('Spend Over Time')).toBeInTheDocument()
  })

  it('shows no bars for empty time_series', () => {
    render(<CostChart timeSeries={[]} />, { withRouter: false })
    expect(screen.getByText('No cost data for this period')).toBeInTheDocument()
  })

  it('renders legend items', () => {
    render(<CostChart timeSeries={mockTimeSeries} />, { withRouter: false })
    expect(screen.getByText('Bedrock')).toBeInTheDocument()
    expect(screen.getByText('Fargate')).toBeInTheDocument()
    expect(screen.getByText('S3')).toBeInTheDocument()
  })
})
