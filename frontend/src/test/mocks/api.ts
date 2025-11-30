import { vi } from 'vitest'
import type { Job } from '../../services/api'

export interface ApiMockConfig {
  fetchJobsResult?: Job[] | Error
  fetchJobDetailsResult?: Job | Error
  createJobResult?: Job | Error
  deleteJobResult?: void | Error
  cancelJobResult?: void | Error
  generateUploadUrlResult?: { upload_url: string; s3_key: string } | Error
}

// Sample job data for testing
export const sampleJob: Job = {
  'job-id': 'job-123',
  'user-id': 'user-456',
  status: 'QUEUED',
  'created-at': '2025-11-19T10:00:00Z',
  'updated-at': '2025-11-19T10:00:00Z',
  'template-id': 'template-789',
  'budget-limit': 100,
  'num-records': 1000,
  'records-generated': 0,
  'tokens-used': 0,
  'cost-estimate': 0,
  config: {
    output_format: 'JSONL',
    model: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
  },
}

export const sampleJobs: Job[] = [
  sampleJob,
  {
    ...sampleJob,
    'job-id': 'job-456',
    status: 'RUNNING',
    'records-generated': 250,
    'tokens-used': 50000,
    'cost-estimate': 1.5,
  },
  {
    ...sampleJob,
    'job-id': 'job-789',
    status: 'COMPLETED',
    'records-generated': 1000,
    'tokens-used': 200000,
    'cost-estimate': 6.0,
  },
]

// Default mock implementations
const defaultConfig: ApiMockConfig = {
  fetchJobsResult: sampleJobs,
  fetchJobDetailsResult: sampleJob,
  createJobResult: sampleJob,
  deleteJobResult: undefined,
  cancelJobResult: undefined,
  generateUploadUrlResult: {
    upload_url: 'https://s3.amazonaws.com/bucket/upload',
    s3_key: 'seed-data/test/file.json',
  },
}

export function createApiMock(config: ApiMockConfig = {}) {
  const mergedConfig = { ...defaultConfig, ...config }

  const fetchJobs = vi.fn().mockImplementation(async () => {
    if (mergedConfig.fetchJobsResult instanceof Error) {
      throw mergedConfig.fetchJobsResult
    }
    return mergedConfig.fetchJobsResult
  })

  const fetchJobDetails = vi.fn().mockImplementation(async () => {
    if (mergedConfig.fetchJobDetailsResult instanceof Error) {
      throw mergedConfig.fetchJobDetailsResult
    }
    return mergedConfig.fetchJobDetailsResult
  })

  const createJob = vi.fn().mockImplementation(async () => {
    if (mergedConfig.createJobResult instanceof Error) {
      throw mergedConfig.createJobResult
    }
    return mergedConfig.createJobResult
  })

  const deleteJob = vi.fn().mockImplementation(async () => {
    if (mergedConfig.deleteJobResult instanceof Error) {
      throw mergedConfig.deleteJobResult
    }
    return mergedConfig.deleteJobResult
  })

  const cancelJob = vi.fn().mockImplementation(async () => {
    if (mergedConfig.cancelJobResult instanceof Error) {
      throw mergedConfig.cancelJobResult
    }
    return mergedConfig.cancelJobResult
  })

  const generateUploadUrl = vi.fn().mockImplementation(async () => {
    if (mergedConfig.generateUploadUrlResult instanceof Error) {
      throw mergedConfig.generateUploadUrlResult
    }
    return mergedConfig.generateUploadUrlResult
  })

  return {
    fetchJobs,
    fetchJobDetails,
    createJob,
    deleteJob,
    cancelJob,
    generateUploadUrl,
    // Helper to reset all mocks
    reset: () => {
      fetchJobs.mockClear()
      fetchJobDetails.mockClear()
      createJob.mockClear()
      deleteJob.mockClear()
      cancelJob.mockClear()
      generateUploadUrl.mockClear()
    },
  }
}

// Common error scenarios
export const apiErrors = {
  unauthorized: new Error('Unauthorized'),
  notFound: new Error('Not found'),
  networkError: new Error('Network Error'),
  serverError: new Error('Internal Server Error'),
  badRequest: new Error('Bad Request'),
  rateLimited: new Error('Too Many Requests'),
}

// Pre-configured mocks for common scenarios
export const defaultApiMock = createApiMock()

export const emptyJobsMock = createApiMock({
  fetchJobsResult: [],
})

export const apiFailureMock = createApiMock({
  fetchJobsResult: apiErrors.networkError,
  fetchJobDetailsResult: apiErrors.networkError,
  createJobResult: apiErrors.networkError,
})
