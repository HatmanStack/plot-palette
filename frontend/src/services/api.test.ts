import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import * as authService from './auth'

// Mock modules before importing the module under test
vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn((fn) => {
          mockAxios._requestInterceptor = fn
          return 0
        }),
      },
    },
    _requestInterceptor: null as ((config: unknown) => Promise<unknown>) | null,
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
} from './api'

describe('API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchJobs', () => {
    it('returns array of jobs from response', async () => {
      const mockJobs = [
        { 'job-id': 'job-1', status: 'RUNNING' },
        { 'job-id': 'job-2', status: 'COMPLETED' },
      ]
      mockAxios.get.mockResolvedValueOnce({ data: { jobs: mockJobs } })

      const result = await fetchJobs()

      expect(mockAxios.get).toHaveBeenCalledWith('/jobs')
      expect(result).toEqual(mockJobs)
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
        'job-id': 'job-123',
        status: 'RUNNING',
        'records-generated': 50,
      }
      mockAxios.get.mockResolvedValueOnce({ data: mockJob })

      const result = await fetchJobDetails('job-123')

      expect(mockAxios.get).toHaveBeenCalledWith('/jobs/job-123')
      expect(result).toEqual(mockJob)
    })
  })

  describe('createJob', () => {
    it('posts job data and returns created job', async () => {
      const jobData = {
        'template-id': 'template-1',
        'seed-data-key': 'seed/file.json',
        'budget-limit': 100,
        'num-records': 1000,
      }
      const createdJob = {
        'job-id': 'new-job-123',
        status: 'QUEUED',
        ...jobData,
      }
      mockAxios.post.mockResolvedValueOnce({ data: createdJob })

      const result = await createJob(jobData)

      expect(mockAxios.post).toHaveBeenCalledWith('/jobs', jobData)
      expect(result).toEqual(createdJob)
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
})
