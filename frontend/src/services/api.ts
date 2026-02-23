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
  template_version?: number
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

export async function updateTemplate(templateId: string, templateData: {
  name: string
  description?: string
  steps: Array<{ id: string; model?: string; model_tier?: string; prompt: string }>
  schema_requirements?: string[]
}): Promise<Template> {
  const { data } = await apiClient.put(`/templates/${templateId}`, templateData)
  return TemplateSchema.parse(data)
}

export async function createTemplate(templateData: {
  name: string
  description?: string
  steps: Array<{ id: string; model?: string; model_tier?: string; prompt: string }>
  schema_requirements?: string[]
}): Promise<Template> {
  const { data } = await apiClient.post('/templates', templateData)
  return TemplateSchema.parse(data)
}

// Cost Analytics schemas
export const CostAnalyticsSchema = z.object({
  summary: z.object({
    total_spend: z.number(),
    job_count: z.number(),
    avg_cost_per_job: z.number(),
    avg_cost_per_record: z.number(),
    budget_efficiency: z.number(),
    most_expensive_job: z.string().nullable(),
  }),
  time_series: z.array(z.object({
    date: z.string(),
    bedrock: z.number(),
    fargate: z.number(),
    s3: z.number(),
    total: z.number(),
  })),
  by_model: z.array(z.object({
    model_id: z.string(),
    model_name: z.string().optional(),
    total: z.number(),
    job_count: z.number(),
  })),
})

export type CostAnalytics = z.infer<typeof CostAnalyticsSchema>

export async function fetchCostAnalytics(period: string = '30d', groupBy: string = 'day'): Promise<CostAnalytics> {
  const { data } = await apiClient.get('/dashboard/cost-analytics', {
    params: { period, group_by: groupBy },
  })
  return CostAnalyticsSchema.parse(data)
}

// Marketplace schemas
export const MarketplaceTemplateSchema = z.object({
  template_id: z.string(),
  name: z.string(),
  description: z.string().default(''),
  user_id: z.string().default(''),
  version: z.number(),
  schema_requirements: z.array(z.string()).default([]),
  step_count: z.number().default(0),
  created_at: z.string().default(''),
})

export type MarketplaceTemplate = z.infer<typeof MarketplaceTemplateSchema>

const MarketplaceResultsSchema = z.object({
  templates: z.array(MarketplaceTemplateSchema),
  count: z.number(),
  total: z.number(),
  last_key: z.string().optional(),
})

export type MarketplaceResults = z.infer<typeof MarketplaceResultsSchema>

export async function searchMarketplaceTemplates(params: {
  q?: string
  sort?: string
  limit?: number
  lastKey?: string
} = {}): Promise<MarketplaceResults> {
  const { data } = await apiClient.get('/templates/marketplace', {
    params: {
      q: params.q,
      sort: params.sort,
      limit: params.limit,
      last_key: params.lastKey,
    },
  })
  return MarketplaceResultsSchema.parse(data)
}

const ForkResultSchema = z.object({
  template_id: z.string(),
  name: z.string().optional(),
  version: z.number().optional(),
  message: z.string().optional(),
})

export async function forkTemplate(templateId: string, name?: string): Promise<z.infer<typeof ForkResultSchema>> {
  const body = name ? { name } : undefined
  const { data } = await apiClient.post(`/templates/${templateId}/fork`, body)
  return ForkResultSchema.parse(data)
}

// Template list for user's own templates
export async function fetchUserTemplates(): Promise<Template[]> {
  const { data } = await apiClient.get('/templates')
  const templates = data.templates || []
  return templates.map((t: unknown) => TemplateSchema.parse(t))
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/templates/${templateId}`)
}

// Notification Preferences schemas
export const NotificationPreferencesSchema = z.object({
  email_enabled: z.boolean().default(false),
  email_address: z.string().nullable().default(null),
  webhook_enabled: z.boolean().default(false),
  webhook_url: z.string().nullable().default(null),
  notify_on_complete: z.boolean().default(true),
  notify_on_failure: z.boolean().default(true),
  notify_on_budget_exceeded: z.boolean().default(true),
})

export type NotificationPreferences = z.infer<typeof NotificationPreferencesSchema>

export async function fetchNotificationPreferences(): Promise<NotificationPreferences> {
  const { data } = await apiClient.get('/settings/notifications')
  return NotificationPreferencesSchema.parse(data)
}

export async function updateNotificationPreferences(
  prefs: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  const { data } = await apiClient.put('/settings/notifications', prefs)
  return NotificationPreferencesSchema.parse(data)
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

// Batch schemas
export const BatchSummarySchema = z.object({
  batch_id: z.string(),
  name: z.string(),
  status: z.string(),
  total_jobs: z.number().default(0),
  completed_jobs: z.number().default(0),
  failed_jobs: z.number().default(0),
  created_at: z.string().default(''),
  total_cost: z.number().default(0),
})

export type BatchSummary = z.infer<typeof BatchSummarySchema>

const BatchJobSchema = z.object({
  job_id: z.string(),
  status: z.string(),
  records_generated: z.number().default(0),
  cost_estimate: z.number().default(0),
  budget_limit: z.number().default(0),
  created_at: z.string().default(''),
  updated_at: z.string().default(''),
})

export type BatchJob = z.infer<typeof BatchJobSchema>

export const BatchDetailSchema = BatchSummarySchema.extend({
  updated_at: z.string().default(''),
  template_id: z.string(),
  template_version: z.number().default(1),
  sweep_config: z.record(z.unknown()).default({}),
  jobs: z.array(BatchJobSchema).default([]),
})

export type BatchDetail = z.infer<typeof BatchDetailSchema>

export async function createBatch(config: {
  name: string
  template_id: string
  template_version: number
  seed_data_path?: string
  base_config: {
    budget_limit: number
    num_records: number
    output_format: string
  }
  sweep: Record<string, unknown[]>
}): Promise<{ batch_id: string; job_count: number; job_ids: string[] }> {
  const { data } = await apiClient.post('/jobs/batch', config)
  return data
}

export async function listBatches(): Promise<BatchSummary[]> {
  const { data } = await apiClient.get('/jobs/batches')
  const batches = data.batches || []
  return batches.map((b: unknown) => BatchSummarySchema.parse(b))
}

export async function fetchBatchDetail(batchId: string): Promise<BatchDetail> {
  const { data } = await apiClient.get(`/jobs/batches/${batchId}`)
  return BatchDetailSchema.parse(data)
}

export async function deleteBatch(batchId: string): Promise<void> {
  await apiClient.delete(`/jobs/batches/${batchId}`)
}

// Seed Data Generation
export const SeedDataGenerationResultSchema = z.object({
  s3_key: z.string(),
  records_generated: z.number(),
  records_invalid: z.number().default(0),
  total_cost: z.number().default(0),
})

export type SeedDataGenerationResult = z.infer<typeof SeedDataGenerationResultSchema>

export async function generateSeedData(params: {
  template_id: string
  count: number
  model_tier?: string
  example_data?: Record<string, unknown>
  instructions?: string
}): Promise<SeedDataGenerationResult> {
  const { data } = await apiClient.post('/seed-data/generate', params)
  return SeedDataGenerationResultSchema.parse(data)
}
