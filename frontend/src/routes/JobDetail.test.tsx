import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import JobDetail from './JobDetail'
import type { Job } from '../services/api'
import { useJobPolling } from '../hooks/useJobPolling'
import { cancelJob, deleteJob, downloadJobExport } from '../services/api'

vi.mock('../hooks/useJobPolling', () => ({
  useJobPolling: vi.fn(),
}))

vi.mock('../services/api', () => ({
  cancelJob: vi.fn(),
  deleteJob: vi.fn(),
  downloadJobExport: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ jobId: 'test-job-12345678' }),
  }
})

const mockUseJobPolling = vi.mocked(useJobPolling)
const mockCancelJob = vi.mocked(cancelJob)
const mockDeleteJob = vi.mocked(deleteJob)
const mockDownloadJobExport = vi.mocked(downloadJobExport)

function createMockJob(overrides: Partial<Job> = {}): Job {
  return {
    'job_id': 'test-job-12345678',
    'user_id': 'user-123',
    status: 'RUNNING',
    'created_at': '2024-01-15T10:30:00Z',
    'updated_at': '2024-01-15T11:30:00Z',
    'template_id': 'template-456',
    'budget_limit': 100,
    'num_records': 1000,
    'records_generated': 500,
    'tokens_used': 25000,
    'cost_estimate': 50,
    ...overrides,
  }
}

function renderJobDetail() {
  return render(
    <MemoryRouter>
      <JobDetail />
    </MemoryRouter>
  )
}

describe('JobDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading state', () => {
    it('shows loading state', () => {
      mockUseJobPolling.mockReturnValue({ data: undefined, isLoading: true, error: null } as any)

      renderJobDetail()

      expect(screen.getByText('Loading job details...')).toBeInTheDocument()
    })
  })

  describe('Error state', () => {
    it('shows error state with error message', () => {
      mockUseJobPolling.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Network failure'),
      } as any)

      renderJobDetail()

      expect(screen.getByText(/Error loading job:/)).toBeInTheDocument()
      expect(screen.getByText(/Network failure/)).toBeInTheDocument()
    })

    it('shows "Job not found" when no error object and no job data', () => {
      mockUseJobPolling.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      } as any)

      renderJobDetail()

      expect(screen.getByText(/Job not found/)).toBeInTheDocument()
    })
  })

  describe('Job display', () => {
    it('renders job ID truncated to 12 chars', () => {
      const job = createMockJob()
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toHaveTextContent('Job test-job-123')
    })

    it('renders StatusBadge with correct status', () => {
      const job = createMockJob({ status: 'RUNNING' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByText('Running')).toBeInTheDocument()
    })

    it('shows created date', () => {
      const job = createMockJob()
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      // The date text is split across child nodes, so use a function matcher
      const dateElement = screen.getByText((_content, element) => {
        return element?.tagName === 'P' && !!element?.textContent?.match(/Created.*Jan.*2024/)
      })
      expect(dateElement).toBeInTheDocument()
    })

    it('shows progress: records_generated / num_records', () => {
      const job = createMockJob({ records_generated: 500, num_records: 1000 })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByText('500 / 1000')).toBeInTheDocument()
    })

    it('shows Back to Dashboard link', () => {
      const job = createMockJob()
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByText(/Back to Dashboard/)).toBeInTheDocument()
    })
  })

  describe('Cost bar color thresholds', () => {
    it('shows green cost bar when under 75%', () => {
      const job = createMockJob({ cost_estimate: 50, budget_limit: 100 })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      const { container } = renderJobDetail()

      // Cost bar should have green class (50% usage)
      const costBar = container.querySelector('.bg-green-500')
      expect(costBar).toBeInTheDocument()
    })

    it('shows yellow cost bar when between 75% and 90%', () => {
      const job = createMockJob({ cost_estimate: 80, budget_limit: 100 })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      const { container } = renderJobDetail()

      const costBar = container.querySelector('.bg-yellow-500')
      expect(costBar).toBeInTheDocument()
    })

    it('shows orange cost bar when over 90%', () => {
      const job = createMockJob({ cost_estimate: 95, budget_limit: 100 })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      const { container } = renderJobDetail()

      const costBar = container.querySelector('.bg-orange-500')
      expect(costBar).toBeInTheDocument()
    })
  })

  describe('Cancel button visibility', () => {
    it('cancel button visible for RUNNING', () => {
      const job = createMockJob({ status: 'RUNNING' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Cancel Job/ })).toBeInTheDocument()
    })

    it('cancel button visible for QUEUED', () => {
      const job = createMockJob({ status: 'QUEUED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Cancel Job/ })).toBeInTheDocument()
    })

    it('cancel button NOT visible for COMPLETED', () => {
      const job = createMockJob({ status: 'COMPLETED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.queryByRole('button', { name: /Cancel Job/ })).not.toBeInTheDocument()
    })
  })

  describe('Delete button visibility', () => {
    it('delete button visible for FAILED', () => {
      const job = createMockJob({ status: 'FAILED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Delete Job/ })).toBeInTheDocument()
    })

    it('delete button visible for COMPLETED', () => {
      const job = createMockJob({ status: 'COMPLETED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Delete Job/ })).toBeInTheDocument()
    })

    it('delete button visible for CANCELLED', () => {
      const job = createMockJob({ status: 'CANCELLED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Delete Job/ })).toBeInTheDocument()
    })
  })

  describe('Download button visibility', () => {
    it('download button visible for COMPLETED', () => {
      const job = createMockJob({ status: 'COMPLETED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.getByRole('button', { name: /Download Exports/ })).toBeInTheDocument()
    })

    it('download button NOT visible for RUNNING', () => {
      const job = createMockJob({ status: 'RUNNING' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)

      renderJobDetail()

      expect(screen.queryByRole('button', { name: /Download Exports/ })).not.toBeInTheDocument()
    })
  })

  describe('Actions', () => {
    it('cancel calls cancelJob and navigates to dashboard', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'RUNNING' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)
      mockCancelJob.mockResolvedValueOnce(undefined)
      vi.spyOn(window, 'confirm').mockReturnValue(true)

      renderJobDetail()

      await user.click(screen.getByRole('button', { name: /Cancel Job/ }))

      await waitFor(() => {
        expect(mockCancelJob).toHaveBeenCalledWith('test-job-12345678')
      })
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
      })
    })

    it('delete calls deleteJob and navigates to dashboard', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'FAILED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)
      mockDeleteJob.mockResolvedValueOnce(undefined)
      vi.spyOn(window, 'confirm').mockReturnValue(true)

      renderJobDetail()

      await user.click(screen.getByRole('button', { name: /Delete Job/ }))

      await waitFor(() => {
        expect(mockDeleteJob).toHaveBeenCalledWith('test-job-12345678')
      })
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
      })
    })

    it('download calls downloadJobExport and opens URL in new window', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'COMPLETED' })
      mockUseJobPolling.mockReturnValue({ data: job, isLoading: false, error: null } as any)
      mockDownloadJobExport.mockResolvedValueOnce({
        download_url: 'https://s3.example.com/export.jsonl',
        filename: 'export.jsonl',
      })
      const mockWindowOpen = vi.spyOn(window, 'open').mockImplementation(() => null)

      renderJobDetail()

      await user.click(screen.getByRole('button', { name: /Download Exports/ }))

      await waitFor(() => {
        expect(mockDownloadJobExport).toHaveBeenCalledWith('test-job-12345678')
      })
      await waitFor(() => {
        expect(mockWindowOpen).toHaveBeenCalledWith('https://s3.example.com/export.jsonl', '_blank')
      })

      mockWindowOpen.mockRestore()
    })
  })
})
