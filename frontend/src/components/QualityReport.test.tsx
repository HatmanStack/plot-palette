import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '../test/test-utils'
import QualityReport from './QualityReport'
import * as api from '../services/api'
import { mockAuthContextAuthenticated } from '../test/test-utils'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof import('../services/api')>('../services/api')
  return {
    ...actual,
    fetchQualityMetrics: vi.fn(),
    triggerQualityScoring: vi.fn(),
  }
})

vi.mock('../hooks/useToast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

const mockFetchQuality = vi.mocked(api.fetchQualityMetrics)
const mockTriggerScoring = vi.mocked(api.triggerQualityScoring)

const completedMetrics: api.QualityMetrics = {
  job_id: 'job-123',
  scored_at: '2025-12-01T10:00:00',
  sample_size: 20,
  total_records: 100,
  model_used_for_scoring: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
  aggregate_scores: {
    coherence: 0.85,
    relevance: 0.9,
    format_compliance: 0.95,
  },
  diversity_score: 0.75,
  overall_score: 0.86,
  record_scores: [
    { record_index: 0, coherence: 0.9, relevance: 0.85, format_compliance: 1.0, detail: 'Good' },
    { record_index: 1, coherence: 0.8, relevance: 0.95, format_compliance: 0.9, detail: 'Fine' },
  ],
  scoring_cost: 0.05,
  status: 'COMPLETED',
  error_message: null,
}

describe('QualityReport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "Run Quality Check" for unscored job', async () => {
    mockFetchQuality.mockResolvedValueOnce(null)

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText('Run Quality Check')).toBeTruthy()
    })
  })

  it('shows scoring progress state', async () => {
    mockFetchQuality.mockResolvedValueOnce({
      ...completedMetrics,
      status: 'SCORING',
    })

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText(/Scoring in progress/)).toBeTruthy()
    })
  })

  it('shows completed report with all dimensions', async () => {
    mockFetchQuality.mockResolvedValueOnce(completedMetrics)

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText('Coherence')).toBeTruthy()
      expect(screen.getByText('Relevance')).toBeTruthy()
      expect(screen.getByText('Format Compliance')).toBeTruthy()
      expect(screen.getByText('Diversity')).toBeTruthy()
    })
  })

  it('shows per-record scores in expandable section', async () => {
    mockFetchQuality.mockResolvedValueOnce(completedMetrics)

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText(/Show.*per-record scores/)).toBeTruthy()
    })

    fireEvent.click(screen.getByText(/Show.*per-record scores/))

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeTruthy()
      expect(screen.getByText('#2')).toBeTruthy()
      expect(screen.getByText('Good')).toBeTruthy()
    })
  })

  it('triggers scoring when button clicked', async () => {
    mockFetchQuality.mockResolvedValueOnce(null)
    mockTriggerScoring.mockResolvedValueOnce()

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText('Run Quality Check')).toBeTruthy()
    })

    fireEvent.click(screen.getByText('Run Quality Check'))

    await waitFor(() => {
      expect(mockTriggerScoring).toHaveBeenCalledWith('job-123')
    })
  })

  it('shows failed state with retry button', async () => {
    mockFetchQuality.mockResolvedValueOnce({
      ...completedMetrics,
      status: 'FAILED',
      error_message: 'Export file not found',
    })

    render(<QualityReport jobId="job-123" />, {
      authContext: mockAuthContextAuthenticated,
    })

    await waitFor(() => {
      expect(screen.getByText(/Export file not found/)).toBeTruthy()
      expect(screen.getByText('Retry')).toBeTruthy()
    })
  })
})
