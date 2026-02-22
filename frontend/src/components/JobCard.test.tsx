import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { ToastProvider } from '../contexts/ToastContext'
import JobCard from './JobCard'
import type { Job } from '../services/api'

// Factory to create mock jobs
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
    'cost_estimate': 0.50,
    ...overrides,
  }
}

describe('JobCard', () => {
  const mockOnDelete = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderJobCard = (job: Job) => {
    return render(
      <BrowserRouter>
        <ToastProvider>
          <JobCard job={job} onDelete={mockOnDelete} />
        </ToastProvider>
      </BrowserRouter>
    )
  }

  describe('Basic rendering', () => {
    it('displays truncated job ID (12 chars)', () => {
      const job = createMockJob({ 'job_id': 'abcdefghijklmnop' })
      renderJobCard(job)

      expect(screen.getByText('Job abcdefghijkl')).toBeInTheDocument()
    })

    it('displays formatted created date', () => {
      const job = createMockJob({ 'created_at': '2024-01-15T10:30:00Z' })
      renderJobCard(job)

      // Date formatting can vary by timezone, so check for key parts
      expect(screen.getByText(/Created/)).toBeInTheDocument()
      expect(screen.getByText(/Jan/)).toBeInTheDocument()
    })

    it('displays status badge', () => {
      const job = createMockJob({ status: 'RUNNING' })
      renderJobCard(job)

      // StatusBadge displays capitalized version (e.g., "Running" not "RUNNING")
      expect(screen.getByText('Running')).toBeInTheDocument()
    })

    it('renders View Details link', () => {
      const job = createMockJob({ 'job_id': 'job-123' })
      renderJobCard(job)

      const link = screen.getByRole('link', { name: /View Details/i })
      expect(link).toHaveAttribute('href', '/jobs/job-123')
    })

    it('renders job link with correct href', () => {
      const job = createMockJob({ 'job_id': 'my-job-id' })
      renderJobCard(job)

      const link = screen.getByRole('link', { name: /Job my-job-id/i })
      expect(link).toHaveAttribute('href', '/jobs/my-job-id')
    })
  })

  describe('Progress bar calculations', () => {
    it('calculates 50% progress correctly', () => {
      const job = createMockJob({
        'num_records': 100,
        'records_generated': 50,
      })
      renderJobCard(job)

      expect(screen.getByText('50 / 100 records')).toBeInTheDocument()
    })

    it('calculates 0% progress when no records generated', () => {
      const job = createMockJob({
        'num_records': 100,
        'records_generated': 0,
      })
      renderJobCard(job)

      expect(screen.getByText('0 / 100 records')).toBeInTheDocument()
    })

    it('calculates 100% progress correctly', () => {
      const job = createMockJob({
        'num_records': 100,
        'records_generated': 100,
      })
      renderJobCard(job)

      expect(screen.getByText('100 / 100 records')).toBeInTheDocument()
    })

    it('handles 0 num-records without division error', () => {
      const job = createMockJob({
        'num_records': 0,
        'records_generated': 0,
      })

      // Should not throw
      expect(() => renderJobCard(job)).not.toThrow()
    })
  })

  describe('Cost progress bar', () => {
    it('displays cost correctly', () => {
      const job = createMockJob({
        'cost_estimate': 50,
        'budget_limit': 100,
      })
      renderJobCard(job)

      expect(screen.getByText('$50.00 / $100.00')).toBeInTheDocument()
    })

    it('handles $0 budget without division error', () => {
      const job = createMockJob({
        'cost_estimate': 0,
        'budget_limit': 0,
      })

      // Should not throw
      expect(() => renderJobCard(job)).not.toThrow()
    })

    it('displays decimal costs correctly', () => {
      const job = createMockJob({
        'cost_estimate': 0.25,
        'budget_limit': 1.50,
      })
      renderJobCard(job)

      expect(screen.getByText('$0.25 / $1.50')).toBeInTheDocument()
    })
  })

  describe('Button visibility by status', () => {
    it('shows Cancel button for QUEUED jobs', async () => {
      const job = createMockJob({ status: 'QUEUED' })
      renderJobCard(job)

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
    })

    it('shows Cancel button for RUNNING jobs', async () => {
      const job = createMockJob({ status: 'RUNNING' })
      renderJobCard(job)

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
    })

    it('shows Download and Delete buttons for COMPLETED jobs', async () => {
      const job = createMockJob({ status: 'COMPLETED' })
      renderJobCard(job)

      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    })

    it('shows Delete button for FAILED jobs', async () => {
      const job = createMockJob({ status: 'FAILED' })
      renderJobCard(job)

      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    })

    it('shows Delete button for CANCELLED jobs', async () => {
      const job = createMockJob({ status: 'CANCELLED' })
      renderJobCard(job)

      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    })
  })

  describe('Button callbacks', () => {
    it('calls onDelete with job ID when Cancel clicked', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'RUNNING', 'job_id': 'cancel-job-123' })
      renderJobCard(job)

      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(mockOnDelete).toHaveBeenCalledTimes(1)
      expect(mockOnDelete).toHaveBeenCalledWith('cancel-job-123')
    })

    it('calls onDelete with job ID when Delete clicked', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'FAILED', 'job_id': 'delete-job-456' })
      renderJobCard(job)

      await user.click(screen.getByRole('button', { name: 'Delete' }))

      expect(mockOnDelete).toHaveBeenCalledTimes(1)
      expect(mockOnDelete).toHaveBeenCalledWith('delete-job-456')
    })

    it('Download button is clickable for COMPLETED jobs', async () => {
      const user = userEvent.setup()
      const job = createMockJob({ status: 'COMPLETED' })
      renderJobCard(job)

      const downloadBtn = screen.getByRole('button', { name: 'Download' })
      // Should not throw - downloads are TODO but button should work
      await user.click(downloadBtn)
    })
  })

  describe('All job statuses', () => {
    const statuses: Job['status'][] = [
      'QUEUED',
      'RUNNING',
      'COMPLETED',
      'FAILED',
      'CANCELLED',
      'BUDGET_EXCEEDED',
    ]

    statuses.forEach((status) => {
      it(`renders without error for ${status} status`, () => {
        const job = createMockJob({ status })
        expect(() => renderJobCard(job)).not.toThrow()
      })
    })
  })
})
