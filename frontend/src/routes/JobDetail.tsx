import { useParams, useNavigate, Link } from 'react-router-dom'
import { useJobPolling } from '../hooks/useJobPolling'
import { cancelJob, deleteJob } from '../services/api'
import StatusBadge from '../components/StatusBadge'

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { data: job, isLoading, error } = useJobPolling(jobId!)

  async function handleCancel() {
    if (!jobId || !confirm('Are you sure you want to cancel this job?')) return

    try {
      await cancelJob(jobId)
      navigate('/dashboard')
    } catch (err) {
      console.error('Failed to cancel job:', err)
    }
  }

  async function handleDelete() {
    if (!jobId || !confirm('Are you sure you want to delete this job?')) return

    try {
      await deleteJob(jobId)
      navigate('/dashboard')
    } catch (err) {
      console.error('Failed to delete job:', err)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-xl text-gray-600">Loading job details...</div>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
        Error loading job: {error instanceof Error ? error.message : 'Job not found'}
      </div>
    )
  }

  const progress = job['num_records'] > 0
    ? (job['records_generated'] / job['num_records']) * 100
    : 0

  const costProgress = job['budget_limit'] > 0
    ? (job['cost_estimate'] / job['budget_limit']) * 100
    : 0

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">Job {job['job_id'].substring(0, 12)}</h1>
            <StatusBadge status={job.status} />
          </div>
          <p className="text-gray-500 mt-1">Created {formatDate(job['created_at'])}</p>
        </div>
        <Link
          to="/dashboard"
          className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
        >
          ← Back to Dashboard
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Progress Card */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Progress</h2>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Records Generated</span>
                  <span className="font-semibold">
                    {job['records_generated']} / {job['num_records']}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-blue-600 h-4 rounded-full transition-all duration-300 flex items-center justify-end pr-2"
                    style={{ width: `${progress}%` }}
                  >
                    {progress > 10 && (
                      <span className="text-xs text-white font-semibold">
                        {progress.toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Cost</span>
                  <span className="font-semibold">
                    ${job['cost_estimate'].toFixed(2)} / ${job['budget_limit'].toFixed(2)}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full transition-all duration-300 ${
                      costProgress > 90 ? 'bg-orange-500' : costProgress > 75 ? 'bg-yellow-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(costProgress, 100)}%` }}
                  />
                </div>
              </div>

              {job.status === 'RUNNING' && (
                <div className="mt-4 text-sm text-gray-600">
                  <p>Estimated time remaining: Calculating...</p>
                  <p className="mt-1">
                    Tokens used: {job['tokens_used'].toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Job Details Card */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Job Details</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Job ID</p>
                <p className="font-mono text-sm">{job['job_id']}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Template ID</p>
                <p className="font-mono text-sm">{job['template_id']}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Created At</p>
                <p className="text-sm">{formatDate(job['created_at'])}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Last Updated</p>
                <p className="text-sm">{formatDate(job['updated_at'])}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Output Format</p>
                <p className="text-sm">{job.config?.output_format || 'JSONL'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Model</p>
                <p className="text-sm">{job.config?.model || 'Default'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions Card */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Actions</h2>

            <div className="space-y-3">
              {job.status === 'COMPLETED' && (
                <button className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors">
                  📥 Download Exports
                </button>
              )}

              {(job.status === 'RUNNING' || job.status === 'QUEUED') && (
                <button
                  onClick={handleCancel}
                  className="w-full px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors"
                >
                  ⏸️ Cancel Job
                </button>
              )}

              {(job.status === 'FAILED' || job.status === 'CANCELLED' || job.status === 'COMPLETED') && (
                <button
                  onClick={handleDelete}
                  className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                >
                  🗑️ Delete Job
                </button>
              )}

              <Link
                to={`/templates/${job['template_id']}`}
                className="block w-full px-4 py-2 bg-gray-600 text-white text-center rounded-md hover:bg-gray-700 transition-colors"
              >
                📝 View Template
              </Link>
            </div>
          </div>

          {/* Cost Breakdown Card */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Cost Breakdown</h2>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Current Cost:</span>
                <span className="font-semibold">${job['cost_estimate'].toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Budget Limit:</span>
                <span className="font-semibold">${job['budget_limit'].toFixed(2)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t">
                <span className="text-gray-600">Remaining:</span>
                <span className={`font-semibold ${
                  job['budget_limit'] - job['cost_estimate'] < job['budget_limit'] * 0.1
                    ? 'text-orange-600'
                    : 'text-green-600'
                }`}>
                  ${(job['budget_limit'] - job['cost_estimate']).toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          {/* Auto-refresh indicator */}
          {(job.status === 'RUNNING' || job.status === 'QUEUED') && (
            <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded text-sm">
              <p className="font-semibold">🔄 Auto-refreshing every 5 seconds</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
