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

// Redirect to login on auth failures
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Base job fields shared across all statuses
const JobBase = z.object({
  job_id: z.string(),
  user_id: z.string().default(''),
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

// Discriminated union: status-specific variants with optional fields
export const JobSchema = z.discriminatedUnion('status', [
  JobBase.extend({ status: z.literal('QUEUED') }),
  JobBase.extend({ status: z.literal('RUNNING'), started_at: z.string().optional() }),
  JobBase.extend({ status: z.literal('COMPLETED'), completed_at: z.string().optional() }),
  JobBase.extend({ status: z.literal('FAILED'), error_message: z.string().optional() }),
  JobBase.extend({ status: z.literal('CANCELLED') }),
  JobBase.extend({ status: z.literal('BUDGET_EXCEEDED') }),
])

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
  return JobSchema.parse(data)
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`)
}

export async function cancelJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`)
}

export async function downloadJobExport(jobId: string): Promise<{ download_url: string; filename: string }> {
  const { data } = await apiClient.get(`/jobs/${jobId}/download`)
  return data
}

// Partial export response schema
const PartialExportSchema = z.object({
  download_url: z.string(),
  filename: z.string(),
  records_available: z.number(),
  format: z.string(),
  expires_in: z.number(),
})

export async function downloadPartialExport(jobId: string): Promise<z.infer<typeof PartialExportSchema>> {
  const { data } = await apiClient.get(`/jobs/${jobId}/download-partial`)
  return PartialExportSchema.parse(data)
}

// Template version schema
export const TemplateVersionSchema = z.object({
  version: z.number(),
  name: z.string().default(''),
  description: z.string().default(''),
  created_at: z.string().default(''),
})

export type TemplateVersion = z.infer<typeof TemplateVersionSchema>

const TemplateVersionListSchema = z.object({
  versions: z.array(TemplateVersionSchema),
  template_id: z.string(),
})

export async function fetchTemplateVersions(templateId: string): Promise<TemplateVersion[]> {
  const { data } = await apiClient.get(`/templates/${templateId}/versions`)
  return TemplateVersionListSchema.parse(data).versions
}

// Template schema for full template data
export const TemplateSchema = z.object({
  template_id: z.string(),
  version: z.number(),
  name: z.string().default(''),
  description: z.string().default(''),
  user_id: z.string().default(''),
  is_public: z.boolean().default(false),
  is_owner: z.boolean().default(false),
  created_at: z.string().default(''),
  steps: z.array(z.object({
    id: z.string(),
    model: z.string().optional(),
    model_tier: z.string().optional(),
    prompt: z.string(),
  })).default([]),
  schema_requirements: z.array(z.string()).default([]),
})

export type Template = z.infer<typeof TemplateSchema>

export async function fetchTemplate(templateId: string, version?: number | 'latest'): Promise<Template> {
  const params = version !== undefined ? `?version=${version}` : ''
  const { data } = await apiClient.get(`/templates/${templateId}${params}`)
  return TemplateSchema.parse(data)
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
