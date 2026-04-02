import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ZodError } from 'zod'
import * as authService from './auth'

// Mock auth module
vi.mock('./auth', () => ({
  getIdToken: vi.fn(),
}))

const mockGetIdToken = vi.mocked(authService.getIdToken)

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Helper to create a mock Response
function mockResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers(),
    redirected: false,
    statusText: 'OK',
    type: 'basic' as ResponseType,
    url: '',
    clone: () => mockResponse(data, status),
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    formData: () => Promise.resolve(new FormData()),
    text: () => Promise.resolve(JSON.stringify(data)),
    bytes: () => Promise.resolve(new Uint8Array()),
  } as Response
}

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
    mockGetIdToken.mockResolvedValue('test-token')
  })

  describe('fetchJobs', () => {
    it('returns array of jobs from response', async () => {
      const mockJobs = [
        { 'job_id': 'job-1', status: 'RUNNING' },
        { 'job_id': 'job-2', status: 'COMPLETED' },
      ]
      mockFetch.mockResolvedValueOnce(mockResponse({ jobs: mockJobs }))

      const result = await fetchJobs()

      expect(mockFetch).toHaveBeenCalledOnce()
      // Zod adds default values for fields not in the mock data
      expect(result).toEqual([
        { 'job_id': 'job-1', status: 'RUNNING', 'user_id': '', 'created_at': '', 'updated_at': '', 'budget_limit': 0, 'num_records': 0, 'records_generated': 0, 'tokens_used': 0, 'cost_estimate': 0 },
        { 'job_id': 'job-2', status: 'COMPLETED', 'user_id': '', 'created_at': '', 'updated_at': '', 'budget_limit': 0, 'num_records': 0, 'records_generated': 0, 'tokens_used': 0, 'cost_estimate': 0 },
      ])
    })

    it('returns empty array when no jobs property', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({}))

      const result = await fetchJobs()

      expect(result).toEqual([])
    })

    it('returns empty array when jobs is null', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ jobs: null }))

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
      mockFetch.mockResolvedValueOnce(mockResponse(mockJob))

      const result = await fetchJobDetails('job-123')

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('/jobs/job-123')
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
      mockFetch.mockResolvedValueOnce(mockResponse(createdJob))

      const result = await createJob(jobData)

      const [url, options] = mockFetch.mock.calls[0]
      expect((url as string)).toContain('/jobs')
      expect((options as RequestInit).method).toBe('POST')
      expect(JSON.parse((options as RequestInit).body as string)).toEqual(jobData)
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
      mockFetch.mockResolvedValueOnce(mockResponse({}, 204))

      await deleteJob('job-to-delete')

      const [url, options] = mockFetch.mock.calls[0]
      expect((url as string)).toContain('/jobs/job-to-delete')
      expect((options as RequestInit).method).toBe('DELETE')
    })
  })

  describe('cancelJob', () => {
    it('sends DELETE request with job ID (same as delete)', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({}, 204))

      await cancelJob('job-to-cancel')

      const [url, options] = mockFetch.mock.calls[0]
      expect((url as string)).toContain('/jobs/job-to-cancel')
      expect((options as RequestInit).method).toBe('DELETE')
    })
  })

  describe('generateUploadUrl', () => {
    it('posts filename and returns upload URL and S3 key', async () => {
      const response = {
        upload_url: 'https://s3.example.com/presigned-url',
        s3_key: 'seed-data/file.json',
      }
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      const result = await generateUploadUrl('file.json', 'application/json')

      const [, options] = mockFetch.mock.calls[0]
      expect(JSON.parse((options as RequestInit).body as string)).toEqual({
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
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      await generateUploadUrl('file.json')

      const [, options] = mockFetch.mock.calls[0]
      expect(JSON.parse((options as RequestInit).body as string)).toEqual({
        filename: 'file.json',
        content_type: 'application/json',
      })
    })
  })

  describe('Auth headers', () => {
    it('adds Authorization header when token exists', async () => {
      mockGetIdToken.mockResolvedValueOnce('test-token-123')
      mockFetch.mockResolvedValueOnce(mockResponse({ jobs: [] }))

      await fetchJobs()

      const [, options] = mockFetch.mock.calls[0]
      const headers = (options as RequestInit).headers as Record<string, string>
      expect(headers['Authorization']).toBe('Bearer test-token-123')
    })

    it('does not add Authorization header when token is null', async () => {
      mockGetIdToken.mockResolvedValueOnce(null)
      mockFetch.mockResolvedValueOnce(mockResponse({ jobs: [] }))

      await fetchJobs()

      const [, options] = mockFetch.mock.calls[0]
      const headers = (options as RequestInit).headers as Record<string, string>
      expect(headers['Authorization']).toBeUndefined()
    })

    it('propagates auth errors instead of swallowing', async () => {
      mockGetIdToken.mockRejectedValueOnce(new Error('Token error'))

      await expect(fetchJobs()).rejects.toThrow('Token error')
    })
  })

  describe('HTTP error handling', () => {
    it('redirects to /login on 401 response', async () => {
      const originalLocation = window.location
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { ...originalLocation, href: '' },
      })

      mockFetch.mockResolvedValueOnce(mockResponse({}, 401))

      await expect(fetchJobs()).rejects.toThrow('Unauthorized')
      expect(window.location.href).toBe('/login')

      Object.defineProperty(window, 'location', {
        writable: true,
        value: originalLocation,
      })
    })

    it('redirects to /login on 403 response', async () => {
      const originalLocation = window.location
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { ...originalLocation, href: '' },
      })

      mockFetch.mockResolvedValueOnce(mockResponse({}, 403))

      await expect(fetchJobs()).rejects.toThrow('Unauthorized')
      expect(window.location.href).toBe('/login')

      Object.defineProperty(window, 'location', {
        writable: true,
        value: originalLocation,
      })
    })

    it('throws with error message from response body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ message: 'Not found' }, 404))

      await expect(fetchJobs()).rejects.toThrow('Not found')
    })

    it('throws with status code when no message in body', async () => {
      const resp = mockResponse({}, 500)
      Object.defineProperty(resp, 'json', {
        value: () => Promise.reject(new Error('no json')),
      })
      mockFetch.mockResolvedValueOnce(resp)

      await expect(fetchJobs()).rejects.toThrow('HTTP error! status: 500')
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
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      const result = await downloadPartialExport('job-abc123')

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('/jobs/job-abc123/download-partial')
      expect(result).toEqual(response)
    })

    it('propagates network errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('fetch failed'))

      await expect(downloadPartialExport('job-abc123')).rejects.toThrow('Network error: unable to reach the server')
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
      mockFetch.mockResolvedValueOnce(mockResponse(templateResponse))

      const result = await fetchTemplate('tmpl-123')

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('/templates/tmpl-123')
      expect(calledUrl).not.toContain('version=')
      expect(result.template_id).toBe('tmpl-123')
      expect(result.version).toBe(2)
    })

    it('appends version=latest query parameter', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ ...templateResponse, version: 3 }))

      const result = await fetchTemplate('tmpl-123', 'latest')

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('version=latest')
      expect(result.version).toBe(3)
    })

    it('appends specific version number as query parameter', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(templateResponse))

      await fetchTemplate('tmpl-123', 2)

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('version=2')
    })

    it('rejects with ZodError for invalid template response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ invalid: true }))

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
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      const result = await fetchTemplateVersions('tmpl-123')

      const calledUrl = mockFetch.mock.calls[0][0] as string
      expect(calledUrl).toContain('/templates/tmpl-123/versions')
      expect(result).toHaveLength(3)
      expect(result[0].version).toBe(3)
    })

    it('rejects with ZodError for malformed response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ no_versions: true }))

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
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      const result = await updateTemplate('tmpl-123', templateData)

      const [url, options] = mockFetch.mock.calls[0]
      expect((url as string)).toContain('/templates/tmpl-123')
      expect((options as RequestInit).method).toBe('PUT')
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
      mockFetch.mockResolvedValueOnce(mockResponse(response))

      const result = await createTemplate(templateData)

      const [url, options] = mockFetch.mock.calls[0]
      expect((url as string)).toContain('/templates')
      expect((options as RequestInit).method).toBe('POST')
      expect(result.template_id).toBe('tmpl-new-456')
      expect(result.version).toBe(1)
    })
  })

  describe('Edge cases', () => {
    it('rejects with ZodError when response data is invalid', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ jobs: [{ invalid_field: true }] }))

      await expect(fetchJobs()).rejects.toThrow(ZodError)
    })

    it('wraps network errors with descriptive message', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      await expect(fetchJobs()).rejects.toThrow('Network error: unable to reach the server')
    })
  })
})
