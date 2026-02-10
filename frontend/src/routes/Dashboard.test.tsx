import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from './Dashboard'
import type { Job } from '../services/api'

// Mock the useJobs hook
const mockRefetch = vi.fn()
const mockUseJobs = vi.fn()
vi.mock('../hooks/useJobs', () => ({
  useJobs: (...args: unknown[]) => mockUseJobs(...args),
}))

// Mock the api module (deleteJob used by Dashboard, downloadJobExport used by JobCard)
const mockDeleteJob = vi.fn()
vi.mock('../services/api', () => ({
  deleteJob: (...args: unknown[]) => mockDeleteJob(...args),
  downloadJobExport: vi.fn(),
}))

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

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: loaded with no jobs
    mockUseJobs.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    })
  })

  const renderDashboard = () => {
    return render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )
  }

  describe('Basic rendering', () => {
    it('renders Dashboard title and Create New Job button', () => {
      renderDashboard()

      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Create New Job/ })).toBeInTheDocument()
    })

    it('renders filter and sort controls', () => {
      renderDashboard()

      expect(screen.getByText('Filter:')).toBeInTheDocument()
      expect(screen.getByText('Sort by:')).toBeInTheDocument()

      const selects = screen.getAllByRole('combobox')
      expect(selects).toHaveLength(2)
    })
  })

  describe('Loading state', () => {
    it('shows loading state', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      expect(screen.getByText('Loading jobs...')).toBeInTheDocument()
      // Should not render the Dashboard heading while loading
      expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument()
    })
  })

  describe('Error state', () => {
    it('shows error state with error message', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Network request failed'),
        refetch: mockRefetch,
      })

      renderDashboard()

      expect(screen.getByText(/Error loading jobs:/)).toBeInTheDocument()
      expect(screen.getByText(/Network request failed/)).toBeInTheDocument()
    })

    it('shows fallback for non-Error objects', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: 'some string error',
        refetch: mockRefetch,
      })

      renderDashboard()

      expect(screen.getByText(/Unknown error/)).toBeInTheDocument()
    })
  })

  describe('Empty state', () => {
    it('shows empty state when no jobs', () => {
      mockUseJobs.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      expect(screen.getByText('No jobs found')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Create Your First Job' })).toBeInTheDocument()
    })
  })

  describe('Job list rendering', () => {
    it('renders job cards for each job', () => {
      const jobs = [
        createMockJob({ 'job_id': 'job-aaaa11112222', status: 'RUNNING' }),
        createMockJob({ 'job_id': 'job-bbbb33334444', status: 'COMPLETED' }),
        createMockJob({ 'job_id': 'job-cccc55556666', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      // JobCard renders truncated IDs (first 12 chars) prefixed with "Job "
      expect(screen.getByText('Job job-aaaa1111')).toBeInTheDocument()
      expect(screen.getByText('Job job-bbbb3333')).toBeInTheDocument()
      expect(screen.getByText('Job job-cccc5555')).toBeInTheDocument()
    })

    it('shows correct job count (filtered/total)', () => {
      const jobs = [
        createMockJob({ 'job_id': 'job-1', status: 'RUNNING' }),
        createMockJob({ 'job_id': 'job-2', status: 'COMPLETED' }),
        createMockJob({ 'job_id': 'job-3', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      expect(screen.getByText('Showing 3 of 3 jobs')).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('filter by RUNNING shows only running jobs', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'running-job-01', status: 'RUNNING' }),
        createMockJob({ 'job_id': 'completed-j-01', status: 'COMPLETED' }),
        createMockJob({ 'job_id': 'failed-job--01', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      // Select "Running" from the filter dropdown
      const filterSelect = screen.getAllByRole('combobox')[0]
      await user.selectOptions(filterSelect, 'RUNNING')

      // Only the running job should be visible
      expect(screen.getByText('Job running-job-')).toBeInTheDocument()
      expect(screen.queryByText('Job completed-j-')).not.toBeInTheDocument()
      expect(screen.queryByText('Job failed-job--')).not.toBeInTheDocument()

      // Count should reflect filtering
      expect(screen.getByText('Showing 1 of 3 jobs')).toBeInTheDocument()
    })

    it('filter by COMPLETED shows only completed jobs', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'running-job-01', status: 'RUNNING' }),
        createMockJob({ 'job_id': 'completed-j-01', status: 'COMPLETED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      const filterSelect = screen.getAllByRole('combobox')[0]
      await user.selectOptions(filterSelect, 'COMPLETED')

      expect(screen.queryByText('Job running-job-')).not.toBeInTheDocument()
      expect(screen.getByText('Job completed-j-')).toBeInTheDocument()
      expect(screen.getByText('Showing 1 of 2 jobs')).toBeInTheDocument()
    })

    it('filter by ALL shows all jobs', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'running-job-01', status: 'RUNNING' }),
        createMockJob({ 'job_id': 'completed-j-01', status: 'COMPLETED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      // Change to RUNNING first, then back to ALL
      const filterSelect = screen.getAllByRole('combobox')[0]
      await user.selectOptions(filterSelect, 'RUNNING')
      expect(screen.getByText('Showing 1 of 2 jobs')).toBeInTheDocument()

      await user.selectOptions(filterSelect, 'ALL')
      expect(screen.getByText('Showing 2 of 2 jobs')).toBeInTheDocument()
    })
  })

  describe('Sorting', () => {
    it('sort by cost orders correctly (highest first)', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'cheap-job-000', 'cost_estimate': 1.00, 'created_at': '2024-01-01T00:00:00Z' }),
        createMockJob({ 'job_id': 'expensive-jo', 'cost_estimate': 99.00, 'created_at': '2024-01-02T00:00:00Z' }),
        createMockJob({ 'job_id': 'medium-job-00', 'cost_estimate': 25.00, 'created_at': '2024-01-03T00:00:00Z' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      // Select "Cost" sort
      const sortSelect = screen.getAllByRole('combobox')[1]
      await user.selectOptions(sortSelect, 'cost')

      // Get the grid container and check the order of job cards
      const jobLinks = screen.getAllByText(/^Job /)
      expect(jobLinks[0]).toHaveTextContent('Job expensive-jo')
      expect(jobLinks[1]).toHaveTextContent('Job medium-job-0')
      expect(jobLinks[2]).toHaveTextContent('Job cheap-job-00')
    })

    it('default sort is by created date (newest first)', () => {
      const jobs = [
        createMockJob({ 'job_id': 'older-job-000', 'created_at': '2024-01-01T00:00:00Z' }),
        createMockJob({ 'job_id': 'newest-job-00', 'created_at': '2024-01-15T00:00:00Z' }),
        createMockJob({ 'job_id': 'middle-job-00', 'created_at': '2024-01-10T00:00:00Z' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      renderDashboard()

      const jobLinks = screen.getAllByText(/^Job /)
      expect(jobLinks[0]).toHaveTextContent('Job newest-job-0')
      expect(jobLinks[1]).toHaveTextContent('Job middle-job-0')
      expect(jobLinks[2]).toHaveTextContent('Job older-job-00')
    })
  })

  describe('Delete functionality', () => {
    it('delete calls deleteJob and refetch when confirmed', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'delete-me-0001', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      mockDeleteJob.mockResolvedValueOnce(undefined)

      // Mock window.confirm to return true
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      renderDashboard()

      const deleteButton = screen.getByRole('button', { name: 'Delete' })
      await user.click(deleteButton)

      expect(confirmSpy).toHaveBeenCalledWith('Are you sure you want to delete this job?')
      expect(mockDeleteJob).toHaveBeenCalledWith('delete-me-0001')
      expect(mockRefetch).toHaveBeenCalledTimes(1)

      confirmSpy.mockRestore()
    })

    it('delete does not call deleteJob when cancelled', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'keep-me-00001', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      // Mock window.confirm to return false
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

      renderDashboard()

      const deleteButton = screen.getByRole('button', { name: 'Delete' })
      await user.click(deleteButton)

      expect(confirmSpy).toHaveBeenCalled()
      expect(mockDeleteJob).not.toHaveBeenCalled()
      expect(mockRefetch).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
    })

    it('handles deleteJob error gracefully', async () => {
      const user = userEvent.setup()
      const jobs = [
        createMockJob({ 'job_id': 'error-job-0001', status: 'FAILED' }),
      ]

      mockUseJobs.mockReturnValue({
        data: jobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      })

      mockDeleteJob.mockRejectedValueOnce(new Error('Delete failed'))

      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      renderDashboard()

      const deleteButton = screen.getByRole('button', { name: 'Delete' })
      await user.click(deleteButton)

      expect(mockDeleteJob).toHaveBeenCalledWith('error-job-0001')
      expect(consoleSpy).toHaveBeenCalledWith('Failed to delete job:', expect.any(Error))
      // refetch should NOT be called when delete fails
      expect(mockRefetch).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
      consoleSpy.mockRestore()
    })
  })
})
