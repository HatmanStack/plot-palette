import axios from 'axios'
import { getIdToken } from './auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_ENDPOINT,
})

// Add auth token to all requests
apiClient.interceptors.request.use(async (config) => {
  try {
    const token = await getIdToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch (error) {
    console.error('Failed to get auth token:', error)
  }
  return config
})

export interface Job {
  job_id: string
  user_id: string
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'BUDGET_EXCEEDED'
  created_at: string
  updated_at: string
  template_id: string
  budget_limit: number
  num_records: number
  records_generated: number
  tokens_used: number
  cost_estimate: number
  config?: {
    output_format?: string
    model?: string
  }
}

export async function fetchJobs(): Promise<Job[]> {
  const { data } = await apiClient.get('/jobs')
  return data.jobs || []
}

export async function fetchJobDetails(jobId: string): Promise<Job> {
  const { data } = await apiClient.get(`/jobs/${jobId}`)
  return data
}

export async function createJob(jobData: {
  template_id: string
  seed_data_path: string
  budget_limit: number
  num_records: number
  output_format?: string
}): Promise<Job> {
  const { data } = await apiClient.post('/jobs', jobData)
  return data
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`)
}

export async function cancelJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`)
}

export async function generateUploadUrl(filename: string, contentType: string = 'application/json'): Promise<{
  upload_url: string
  s3_key: string
}> {
  const { data } = await apiClient.post('/seed-data/upload', {
    filename,
    content_type: contentType,
  })
  return data
}
