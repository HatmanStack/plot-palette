import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import CreateJob from './CreateJob'
import { ToastProvider } from '../contexts/ToastContext'
import * as api from '../services/api'
import type { SeedDataGenerationResult } from '../services/api'

// Mock the API module
vi.mock('../services/api', () => ({
  createJob: vi.fn(),
  generateUploadUrl: vi.fn(),
  fetchTemplateVersions: vi.fn(),
  generateSeedData: vi.fn(),
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
const mockFetchTemplateVersions = vi.mocked(api.fetchTemplateVersions)
const mockGenerateSeedData = vi.mocked(api.generateSeedData)

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
}

describe('CreateJob', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchTemplateVersions.mockResolvedValue([
      { version: 3, name: 'v3', description: '', created_at: '2025-01-03T00:00:00' },
      { version: 2, name: 'v2', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: 'v1', description: '', created_at: '2025-01-01T00:00:00' },
    ])
  })

  const renderCreateJob = () => {
    return render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <ToastProvider>
            <CreateJob />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>
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

      expect(screen.getByRole('heading', { name: 'Seed Data' })).toBeInTheDocument()
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
      expect(screen.getByRole('heading', { name: 'Seed Data' })).toBeInTheDocument()

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

  describe('Template version selection', () => {
    it('shows version dropdown after template ID is entered', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      await waitFor(() => {
        expect(screen.getByLabelText('Template Version')).toBeInTheDocument()
      })
    })

    it('defaults to Latest version', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      await waitFor(() => {
        const select = screen.getByLabelText('Template Version') as HTMLSelectElement
        expect(select.value).toBe('latest')
      })
    })

    it('shows version in review step', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      // Navigate to step 4
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Version is shown in review
      expect(screen.getByText('Latest')).toBeInTheDocument()
    })
  })

  describe('Step 3: Job Configuration', () => {
    it('renders budget limit input', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByText(/Budget Limit/)).toBeInTheDocument()
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

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByRole('button', { name: 'Create Job' })).toBeInTheDocument()
    })

    it('shows error when submitting without required fields', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(screen.getByText('Please select a template')).toBeInTheDocument()
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
        'job_id': 'new-job-123',
        'user_id': 'user-1',
        status: 'QUEUED',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'template_id': 'template-1',
        'budget_limit': 10,
        'num_records': 100,
        'records_generated': 0,
        'tokens_used': 0,
        'cost_estimate': 0,
      })

      renderCreateJob()

      // Fill in template ID
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      // Go to step 2 and upload file
      await user.click(screen.getByRole('button', { name: 'Next' }))

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

  describe('Template version in payload', () => {
    it('passes template_version when specific version is selected', async () => {
      const user = userEvent.setup()

      mockGenerateUploadUrl.mockResolvedValueOnce({
        upload_url: 'https://s3.example.com/upload',
        s3_key: 'seed-data/test-file.json',
      })
      mockCreateJob.mockResolvedValueOnce({
        'job_id': 'new-job-456',
        'user_id': 'user-1',
        status: 'QUEUED',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'template_id': 'template-1',
        'budget_limit': 10,
        'num_records': 100,
        'records_generated': 0,
        'tokens_used': 0,
        'cost_estimate': 0,
      })

      renderCreateJob()

      // Fill in template ID
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      // Wait for version dropdown and select version 2
      await waitFor(() => {
        expect(screen.getByLabelText('Template Version')).toBeInTheDocument()
      })
      await user.selectOptions(screen.getByLabelText('Template Version'), '2')

      // Navigate to step 2 and upload file
      await user.click(screen.getByRole('button', { name: 'Next' }))
      const file = new File(['{"data": "test"}'], 'test.json', { type: 'application/json' })
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(fileInput, file)

      // Navigate to step 3 (config) and step 4 (review)
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Submit
      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(mockCreateJob).toHaveBeenCalledWith(
          expect.objectContaining({
            template_id: 'my-template',
            template_version: 2,
          })
        )
      })
    })

    it('omits template_version when Latest is selected', async () => {
      const user = userEvent.setup()

      mockGenerateUploadUrl.mockResolvedValueOnce({
        upload_url: 'https://s3.example.com/upload',
        s3_key: 'seed-data/test-file.json',
      })
      mockCreateJob.mockResolvedValueOnce({
        'job_id': 'new-job-789',
        'user_id': 'user-1',
        status: 'QUEUED',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'template_id': 'template-1',
        'budget_limit': 10,
        'num_records': 100,
        'records_generated': 0,
        'tokens_used': 0,
        'cost_estimate': 0,
      })

      renderCreateJob()

      // Fill in template ID (keeps default "Latest")
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'my-template')

      // Navigate through all steps
      await user.click(screen.getByRole('button', { name: 'Next' }))
      const file = new File(['{"data": "test"}'], 'test.json', { type: 'application/json' })
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(fileInput, file)
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Submit
      await user.click(screen.getByRole('button', { name: 'Create Job' }))

      await waitFor(() => {
        expect(mockCreateJob).toHaveBeenCalled()
        const payload = mockCreateJob.mock.calls[0][0]
        expect(payload).not.toHaveProperty('template_version')
      })
    })
  })

  describe('Seed data mode toggle', () => {
    it('step 2 shows upload and generate options', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      await user.click(screen.getByRole('button', { name: 'Next' }))

      expect(screen.getByLabelText('Upload File')).toBeInTheDocument()
      expect(screen.getByLabelText('Generate from Schema')).toBeInTheDocument()
    })

    it('switching to generate mode shows SeedDataGenerator', async () => {
      const user = userEvent.setup()
      renderCreateJob()

      // Enter template ID first (needed for SeedDataGenerator)
      await user.type(screen.getByPlaceholderText('Enter template ID'), 'tmpl-123')
      await user.click(screen.getByRole('button', { name: 'Next' }))

      // Default mode is upload
      expect(screen.getByText(/Seed Data File/)).toBeInTheDocument()

      // Switch to generate mode
      await user.click(screen.getByLabelText('Generate from Schema'))

      // Should show SeedDataGenerator elements
      expect(screen.getByText(/Number of Records/)).toBeInTheDocument()
      expect(screen.getByText(/Model Tier/)).toBeInTheDocument()
    })
  })

  describe('Error handling', () => {
    it('displays error message when API fails', async () => {
      const user = userEvent.setup()

      mockGenerateUploadUrl.mockRejectedValueOnce(new Error('Upload failed'))

      renderCreateJob()

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
