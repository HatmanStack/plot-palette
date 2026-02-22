import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ZodError } from 'zod'
import axios from 'axios'
import * as authService from './auth'

// Mock modules before importing the module under test
vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn((fn) => {
          mockAxios._requestInterceptor = fn
          return 0
        }),
      },
      response: {
        use: vi.fn((_onFulfilled, onRejected) => {
          mockAxios._responseErrorInterceptor = onRejected
          return 0
        }),
      },
    },
    _requestInterceptor: null as ((config: unknown) => Promise<unknown>) | null,
    _responseErrorInterceptor: null as ((error: unknown) => unknown) | null,
  }
  return { default: mockAxios }
})

vi.mock('./auth', () => ({
  getIdToken: vi.fn(),
}))

const mockGetIdToken = vi.mocked(authService.getIdToken)
const mockAxios = vi.mocked(axios)

// Import the module after mocking
import {
  fetchJobs,
  fetchJobDetails,
  createJob,
  deleteJob,
  cancelJob,
  generateUploadUrl,
  downloadPartialExport,
  fetchTemplate,
  fetchTemplateVersions,
  updateTemplate,
  createTemplate,
} from './api'

describe('API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchJobs', () => {
    it('returns array of jobs from response', async () => {
      const mockJobs = [
        { 'job_id': 'job-1', status: 'RUNNING' },
        { 'job_id': 'job-2', status: 'COMPLETED' },
      ]
      mockAxios.get.mockResolvedValueOnce({ data: { jobs: mockJobs } })

      const result = await fetchJobs()

      expect(mockAxios.get).toHaveBeenCalledWith('/jobs')
      // Zod adds default values for fields not in the mock data
      expect(result).toEqual([
        { 'job_id': 'job-1', status: 'RUNNING', 'user_id': '', 'created_at': '', 'updated_at': '', 'budget_limit': 0, 'num_records': 0, 'records_generated': 0, 'tokens_used': 0, 'cost_estimate': 0 },
        { 'job_id': 'job-2', status: 'COMPLETED', 'user_id': '', 'created_at': '', 'updated_at': '', 'budget_limit': 0, 'num_records': 0, 'records_generated': 0, 'tokens_used': 0, 'cost_estimate': 0 },
      ])
    })

    it('returns empty array when no jobs property', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: {} })

      const result = await fetchJobs()

      expect(result).toEqual([])
    })

    it('returns empty array when jobs is null', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: { jobs: null } })

      const result = await fetchJobs()

      expect(result).toEqual([])
    })
  })

  describe('fetchJobDetails', () => {
    it('fetches job by ID', async () => {
      const mockJob = {
        'job_id': 'job-123',
        status: 'RUNNING',
        'records_generated': 50,
      }
      mockAxios.get.mockResolvedValueOnce({ data: mockJob })

      const result = await fetchJobDetails('job-123')

      expect(mockAxios.get).toHaveBeenCalledWith('/jobs/job-123')
      // Zod adds default values for fields not in the mock data
      expect(result).toEqual({
        'job_id': 'job-123', status: 'RUNNING', 'records_generated': 50,
        'user_id': '', 'created_at': '', 'updated_at': '', 'budget_limit': 0, 'num_records': 0, 'tokens_used': 0, 'cost_estimate': 0,
      })
    })
  })

  describe('createJob', () => {
    it('posts job data and returns Zod-validated job', async () => {
      const jobData = {
        'template_id': 'template-1',
        'seed_data_path': 'seed/file.json',
        'budget_limit': 100,
        'num_records': 1000,
      }
      const createdJob = {
        'job_id': 'new-job-123',
        status: 'QUEUED',
        'budget_limit': 100,
        'num_records': 1000,
      }
      mockAxios.post.mockResolvedValueOnce({ data: createdJob })

      const result = await createJob(jobData)

      expect(mockAxios.post).toHaveBeenCalledWith('/jobs', jobData)
      // Zod adds default values for fields not in the response
      expect(result).toEqual({
        'job_id': 'new-job-123', status: 'QUEUED',
        'user_id': '', 'created_at': '', 'updated_at': '',
        'budget_limit': 100, 'num_records': 1000,
        'records_generated': 0, 'tokens_used': 0, 'cost_estimate': 0,
      })
    })
  })

  describe('deleteJob', () => {
    it('sends DELETE request with job ID', async () => {
      mockAxios.delete.mockResolvedValueOnce({})

      await deleteJob('job-to-delete')

      expect(mockAxios.delete).toHaveBeenCalledWith('/jobs/job-to-delete')
    })
  })

  describe('cancelJob', () => {
    it('sends DELETE request with job ID (same as delete)', async () => {
      mockAxios.delete.mockResolvedValueOnce({})

      await cancelJob('job-to-cancel')

      // Note: cancelJob uses the same endpoint as deleteJob
      expect(mockAxios.delete).toHaveBeenCalledWith('/jobs/job-to-cancel')
    })
  })

  describe('generateUploadUrl', () => {
    it('posts filename and returns upload URL and S3 key', async () => {
      const response = {
        upload_url: 'https://s3.example.com/presigned-url',
        s3_key: 'seed-data/file.json',
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      const result = await generateUploadUrl('file.json', 'application/json')

      expect(mockAxios.post).toHaveBeenCalledWith('/seed-data/upload', {
        filename: 'file.json',
        content_type: 'application/json',
      })
      expect(result).toEqual(response)
    })

    it('uses default content type when not provided', async () => {
      const response = {
        upload_url: 'https://s3.example.com/presigned-url',
        s3_key: 'seed-data/file.json',
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      await generateUploadUrl('file.json')

      expect(mockAxios.post).toHaveBeenCalledWith('/seed-data/upload', {
        filename: 'file.json',
        content_type: 'application/json',
      })
    })
  })

  describe('Auth interceptor', () => {
    it('adds Authorization header when token exists', async () => {
      mockGetIdToken.mockResolvedValueOnce('test-token-123')

      // Get the registered interceptor and call it
      const interceptor = mockAxios._requestInterceptor
      expect(interceptor).not.toBeNull()

      const config = { headers: {} as Record<string, string> }
      const result = await interceptor!(config)

      expect(mockGetIdToken).toHaveBeenCalled()
      expect((result as { headers: { Authorization: string } }).headers.Authorization).toBe('Bearer test-token-123')
    })

    it('does not add Authorization header when token is null', async () => {
      mockGetIdToken.mockResolvedValueOnce(null)

      const interceptor = mockAxios._requestInterceptor
      const config = { headers: {} as Record<string, string> }
      const result = await interceptor!(config)

      expect((result as { headers: Record<string, string> }).headers.Authorization).toBeUndefined()
    })

    it('continues without error when getIdToken throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetIdToken.mockRejectedValueOnce(new Error('Token error'))

      const interceptor = mockAxios._requestInterceptor
      const config = { headers: {} as Record<string, string> }
      const result = await interceptor!(config)

      expect(consoleSpy).toHaveBeenCalled()
      expect((result as { headers: Record<string, string> }).headers.Authorization).toBeUndefined()

      consoleSpy.mockRestore()
    })
  })

  describe('Response interceptor', () => {
    it('redirects to /login on 401 response', async () => {
      const interceptor = mockAxios._responseErrorInterceptor
      expect(interceptor).not.toBeNull()

      // Mock window.location
      const originalLocation = window.location
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { ...originalLocation, href: '' },
      })

      const error = { response: { status: 401 } }
      await expect(interceptor!(error)).rejects.toEqual(error)

      expect(window.location.href).toBe('/login')

      Object.defineProperty(window, 'location', {
        writable: true,
        value: originalLocation,
      })
    })

    it('redirects to /login on 403 response', async () => {
      const interceptor = mockAxios._responseErrorInterceptor
      const originalLocation = window.location
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { ...originalLocation, href: '' },
      })

      const error = { response: { status: 403 } }
      await expect(interceptor!(error)).rejects.toEqual(error)

      expect(window.location.href).toBe('/login')

      Object.defineProperty(window, 'location', {
        writable: true,
        value: originalLocation,
      })
    })

    it('does not redirect on other error codes', async () => {
      const interceptor = mockAxios._responseErrorInterceptor
      const originalHref = window.location.href

      const error = { response: { status: 500 } }
      await expect(interceptor!(error)).rejects.toEqual(error)

      expect(window.location.href).toBe(originalHref)
    })
  })

  describe('downloadPartialExport', () => {
    it('calls correct endpoint and returns Zod-parsed response', async () => {
      const response = {
        download_url: 'https://s3.example.com/partial.jsonl',
        filename: 'job-abc123-partial.jsonl',
        records_available: 50,
        format: 'jsonl',
        expires_in: 3600,
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      const result = await downloadPartialExport('job-abc123')

      expect(mockAxios.get).toHaveBeenCalledWith('/jobs/job-abc123/download-partial')
      expect(result).toEqual(response)
    })

    it('propagates network errors', async () => {
      mockAxios.get.mockRejectedValueOnce(new Error('Network Error'))

      await expect(downloadPartialExport('job-abc123')).rejects.toThrow('Network Error')
    })
  })

  describe('fetchTemplate', () => {
    const templateResponse = {
      template_id: 'tmpl-123',
      version: 2,
      name: 'My Template',
      description: 'A template',
      user_id: 'user-1',
      is_public: false,
      is_owner: true,
      created_at: '2025-01-01T00:00:00',
      steps: [{ id: 'step1', prompt: 'Generate text' }],
      schema_requirements: ['author.name'],
    }

    it('fetches template without version parameter', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: templateResponse })

      const result = await fetchTemplate('tmpl-123')

      expect(mockAxios.get).toHaveBeenCalledWith('/templates/tmpl-123')
      expect(result.template_id).toBe('tmpl-123')
      expect(result.version).toBe(2)
    })

    it('appends version=latest query parameter', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: { ...templateResponse, version: 3 } })

      const result = await fetchTemplate('tmpl-123', 'latest')

      expect(mockAxios.get).toHaveBeenCalledWith('/templates/tmpl-123?version=latest')
      expect(result.version).toBe(3)
    })

    it('appends specific version number as query parameter', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: templateResponse })

      await fetchTemplate('tmpl-123', 2)

      expect(mockAxios.get).toHaveBeenCalledWith('/templates/tmpl-123?version=2')
    })

    it('rejects with ZodError for invalid template response', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: { invalid: true } })

      await expect(fetchTemplate('tmpl-123')).rejects.toThrow(ZodError)
    })
  })

  describe('fetchTemplateVersions', () => {
    it('calls correct endpoint and returns parsed versions', async () => {
      const response = {
        template_id: 'tmpl-123',
        versions: [
          { version: 3, name: 'v3', description: '', created_at: '2025-01-03T00:00:00' },
          { version: 2, name: 'v2', description: '', created_at: '2025-01-02T00:00:00' },
          { version: 1, name: 'v1', description: '', created_at: '2025-01-01T00:00:00' },
        ],
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      const result = await fetchTemplateVersions('tmpl-123')

      expect(mockAxios.get).toHaveBeenCalledWith('/templates/tmpl-123/versions')
      expect(result).toHaveLength(3)
      expect(result[0].version).toBe(3)
    })

    it('rejects with ZodError for malformed response', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: { no_versions: true } })

      await expect(fetchTemplateVersions('tmpl-123')).rejects.toThrow(ZodError)
    })
  })

  describe('updateTemplate', () => {
    it('sends PUT request with template data and returns parsed response', async () => {
      const templateData = {
        name: 'Updated Name',
        steps: [{ id: 'step1', prompt: 'Updated prompt' }],
      }
      const response = {
        template_id: 'tmpl-123',
        version: 3,
        name: 'Updated Name',
        steps: [{ id: 'step1', prompt: 'Updated prompt' }],
      }
      mockAxios.put.mockResolvedValueOnce({ data: response })

      const result = await updateTemplate('tmpl-123', templateData)

      expect(mockAxios.put).toHaveBeenCalledWith('/templates/tmpl-123', templateData)
      expect(result.version).toBe(3)
      expect(result.name).toBe('Updated Name')
    })
  })

  describe('createTemplate', () => {
    it('sends POST request with template data and returns parsed response', async () => {
      const templateData = {
        name: 'New Template',
        steps: [{ id: 'step1', prompt: 'Generate text' }],
      }
      const response = {
        template_id: 'tmpl-new-456',
        version: 1,
        name: 'New Template',
        steps: [{ id: 'step1', prompt: 'Generate text' }],
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      const result = await createTemplate(templateData)

      expect(mockAxios.post).toHaveBeenCalledWith('/templates', templateData)
      expect(result.template_id).toBe('tmpl-new-456')
      expect(result.version).toBe(1)
    })
  })

  describe('Edge cases', () => {
    it('rejects with ZodError when response data is invalid', async () => {
      mockAxios.get.mockResolvedValueOnce({
        data: { jobs: [{ invalid_field: true }] },
      })

      await expect(fetchJobs()).rejects.toThrow(ZodError)
    })

    it('propagates network errors without swallowing', async () => {
      mockAxios.get.mockRejectedValueOnce(new Error('Network Error'))

      await expect(fetchJobs()).rejects.toThrow('Network Error')
    })
  })
})
