import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../test/test-utils'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchCostAnalytics: vi.fn(),
  }
})

import { fetchCostAnalytics } from '../services/api'
import CostAnalytics from './CostAnalytics'

const mockData = {
  summary: {
    total_spend: 50.25,
    job_count: 5,
    avg_cost_per_job: 10.05,
    avg_cost_per_record: 0.05,
    budget_efficiency: 0.5,
    most_expensive_job: 'job-1',
  },
  time_series: [
    { date: '2026-02-20', bedrock: 5.0, fargate: 1.0, s3: 0.2, total: 6.2 },
    { date: '2026-02-21', bedrock: 10.0, fargate: 2.0, s3: 0.5, total: 12.5 },
  ],
  by_model: [
    { model_id: 'meta.llama3-1-8b-instruct-v1:0', model_name: 'Llama 3.1 8B', total: 20.0, job_count: 3 },
  ],
}

describe('CostAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads data on mount with default 30d period', async () => {
    vi.mocked(fetchCostAnalytics).mockResolvedValueOnce(mockData)

    render(<CostAnalytics />, {
      authContext: {
        isAuthenticated: true,
        idToken: 'mock-token',
        login: async () => {},
        signup: async () => {},
        logout: () => {},
        loading: false,
      },
    })

    await waitFor(() => {
      expect(screen.getByText('Cost Analytics')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(fetchCostAnalytics).toHaveBeenCalledWith('30d', 'day')
    })
  })

  it('switches period when button clicked', async () => {
    vi.mocked(fetchCostAnalytics).mockResolvedValue(mockData)

    render(<CostAnalytics />, {
      authContext: {
        isAuthenticated: true,
        idToken: 'mock-token',
        login: async () => {},
        signup: async () => {},
        logout: () => {},
        loading: false,
      },
    })

    await waitFor(() => {
      expect(screen.getByText('$50.25')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('7 Days'))

    await waitFor(() => {
      expect(fetchCostAnalytics).toHaveBeenCalledWith('7d', 'day')
    })
  })

  it('shows loading state', () => {
    vi.mocked(fetchCostAnalytics).mockReturnValue(new Promise(() => {}))

    render(<CostAnalytics />, {
      authContext: {
        isAuthenticated: true,
        idToken: 'mock-token',
        login: async () => {},
        signup: async () => {},
        logout: () => {},
        loading: false,
      },
    })

    expect(screen.getByText('Cost Analytics')).toBeInTheDocument()
  })
})
