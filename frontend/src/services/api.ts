import axios from 'axios'
import { z } from 'zod'
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

// Runtime validation schema
export const JobSchema = z.object({
  job_id: z.string(),
  user_id: z.string().default(''),
  status: z.enum(['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED']),
  created_at: z.string().default(''),
  updated_at: z.string().default(''),
  template_id: z.string().optional(),
  budget_limit: z.number().default(0),
  num_records: z.number().default(0),
  records_generated: z.number().default(0),
  tokens_used: z.number().default(0),
  cost_estimate: z.number().default(0),
  config: z.object({
    output_format: z.string().optional(),
    model: z.string().optional(),
  }).optional(),
})

export type Job = z.infer<typeof JobSchema>

export async function fetchJobs(): Promise<Job[]> {
  const { data } = await apiClient.get('/jobs')
  const jobs = data.jobs || []
  return jobs.map((job: unknown) => JobSchema.parse(job))
}

export async function fetchJobDetails(jobId: string): Promise<Job> {
  const { data } = await apiClient.get(`/jobs/${jobId}`)
  return JobSchema.parse(data)
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
