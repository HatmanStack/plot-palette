import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CreateJob from './CreateJob'
import * as api from '../services/api'

// Mock the API module
vi.mock('../services/api', () => ({
  createJob: vi.fn(),
  generateUploadUrl: vi.fn(),
}))

// Mock axios for S3 upload
vi.mock('axios', () => ({
  default: {
    put: vi.fn(),
  },
}))

// Mock react-router-dom's useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockCreateJob = vi.mocked(api.createJob)
const mockGenerateUploadUrl = vi.mocked(api.generateUploadUrl)

describe('CreateJob', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderCreateJob = () => {
    return render(
      <MemoryRouter>
        <CreateJob />
      </MemoryRouter>
    )
  }

  describe('Form rendering', () => {
    it('renders the page title', () => {
      renderCreateJob()
      expect(screen.getByRole('heading', { name: 'Create New Job' })).toBeInTheDocument()
    })

    it('renders step 1 by default with template selection', () => {
      renderCreateJob()
      expect(screen.getByRole('heading', { name: 'Select Template' })).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Enter template ID')).toBeInTheDocument()
    })

    it('shows Cancel and Next buttons', () => {
      renderCreateJob()
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })
  })

  describe('Step navigation', () => {
    it('navigates to step 2 when Next is clicked', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByRole('heading', { name: 'Upload Seed Data' })).toBeInTheDocument()
    })

    it('navigates to step 3 from step 2', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByRole('heading', { name: 'Job Configuration' })).toBeInTheDocument()
    })

    it('navigates to step 4 (Review) from step 3', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByRole('heading', { name: 'Review & Create' })).toBeInTheDocument()
    })

    it('can navigate back with Previous button', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      expect(screen.getByRole('heading', { name: 'Upload Seed Data' })).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Previous' }))
      expect(screen.getByRole('heading', { name: 'Select Template' })).toBeInTheDocument()
    })

    it('Cancel on step 1 navigates to dashboard', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  describe('Step 3: Job Configuration', () => {
    it('renders budget limit input', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Label exists but has no for/id association, so check by text
      expect(screen.getByText(/Budget Limit/)).toBeInTheDocument()
      // Should have number inputs (budget and records)
      const spinbuttons = screen.getAllByRole('spinbutton')
      expect(spinbuttons.length).toBeGreaterThanOrEqual(1)
    })

    it('renders number of records input', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText(/Number of Records/)).toBeInTheDocument()
    })

    it('renders output format selector', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText(/Output Format/)).toBeInTheDocument()
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })
  })

  describe('Step 4: Review and Submit', () => {
    it('shows Create Job button on step 4', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      // Navigate to step 4
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByRole('button', { name: 'Create Job' })).toBeInTheDocument()
    })

    it('shows error when submitting without required fields', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      // Navigate to step 4 without filling required fields
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(screen.getByText('Please complete all required fields')).toBeInTheDocument()
      })
    })
  })

  describe('Successful submission', () => {
    it('navigates to job details on successful creation', async () => {
      const user = userEvent.setup()

      mockGenerateUploadUrl.mockResolvedValueOnce({
        upload_url: 'https://s3.example.com/upload',
        s3_key: 'seed-data/test-file.json',
      })
      mockCreateJob.mockResolvedValueOnce({
        'job-id': 'new-job-123',
        'user-id': 'user-1',
        status: 'QUEUED',
        'created-at': '2024-01-01T00:00:00Z',
        'updated-at': '2024-01-01T00:00:00Z',
        'template-id': 'template-1',
        'budget-limit': 10,
        'num-records': 100,
        'records-generated': 0,
        'tokens-used': 0,
        'cost-estimate': 0,
      })

      renderCreateJob()

      // Fill in template ID
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      // Go to step 2 and upload file
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Create a mock file - find input by type since no label association
      const file = new File(['{"data": "test"}'], 'test.json', { type: 'application/json' })
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(fileInput, file)

      // Go to step 3 (config) and step 4 (review)
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Submit
      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/jobs/new-job-123')
      })
    })
  })

  describe('Error handling', () => {
    it('displays error message when API fails', async () => {
      const user = userEvent.setup()

      mockGenerateUploadUrl.mockRejectedValueOnce(new Error('Upload failed'))

      renderCreateJob()

      // Fill required fields
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')
      await user.click(screen.getByRole('button', { name: 'Next' }))

      const file = new File(['test'], 'test.json', { type: 'application/json' })
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(fileInput, file)

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(screen.getByText('Upload failed')).toBeInTheDocument()
      })
    })
  })
})
