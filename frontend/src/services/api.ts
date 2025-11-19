import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_ENDPOINT,
})

// Add auth token to all requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('idToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface Job {
  'job-id': string
  'user-id': string
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'BUDGET_EXCEEDED'
  'created-at': string
  'updated-at': string
  'template-id': string
  'budget-limit': number
  'num-records': number
  'records-generated': number
  'tokens-used': number
  'cost-estimate': number
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
  'template-id': string
  'seed-data-key': string
  'budget-limit': number
  'num-records': number
  'output-format'?: string
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
