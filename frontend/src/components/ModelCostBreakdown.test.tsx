import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import ModelCostBreakdown from './ModelCostBreakdown'

const mockByModel = [
  { model_id: 'anthropic.claude-3-5-sonnet-20241022-v2:0', model_name: 'Claude 3.5 Sonnet', total: 25.50, job_count: 5 },
  { model_id: 'meta.llama3-1-8b-instruct-v1:0', model_name: 'Llama 3.1 8B', total: 8.25, job_count: 10 },
]

describe('ModelCostBreakdown', () => {
  it('renders table with model rows sorted by cost', () => {
    render(<ModelCostBreakdown byModel={mockByModel} />, { withRouter: false })

    expect(screen.getByText('Claude 3.5 Sonnet')).toBeInTheDocument()
    expect(screen.getByText('Llama 3.1 8B')).toBeInTheDocument()
    expect(screen.getByText('$25.50')).toBeInTheDocument()
    expect(screen.getByText('$8.25')).toBeInTheDocument()
  })

  it('maps model IDs to friendly names', () => {
    render(<ModelCostBreakdown byModel={mockByModel} />, { withRouter: false })

    expect(screen.getByText('Claude 3.5 Sonnet')).toBeInTheDocument()
    expect(screen.getByText('Llama 3.1 8B')).toBeInTheDocument()
  })

  it('shows "No model usage data" for empty array', () => {
    render(<ModelCostBreakdown byModel={[]} />, { withRouter: false })
    expect(screen.getByText('No model usage data')).toBeInTheDocument()
  })

  it('renders job count column', () => {
    render(<ModelCostBreakdown byModel={mockByModel} />, { withRouter: false })

    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })
})
