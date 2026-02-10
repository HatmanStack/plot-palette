import { Link } from 'react-router-dom'
import StatusBadge from './StatusBadge'
import type { Job } from '../services/api'

interface JobCardProps {
  job: Job
  onDelete: (jobId: string) => void
}

export default function JobCard({ job, onDelete }: JobCardProps) {
  const progress = job['num_records'] > 0
    ? (job['records_generated'] / job['num_records']) * 100
    : 0

  const costProgress = job['budget_limit'] > 0
    ? (job['cost_estimate'] / job['budget_limit']) * 100
    : 0

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <div>
          <Link
            to={`/jobs/${job['job_id']}`}
            className="text-lg font-semibold text-gray-900 hover:text-blue-600"
          >
            Job {job['job_id'].substring(0, 8)}
          </Link>
          <p className="text-sm text-gray-500 mt-1">
            Created {formatDate(job['created_at'])}
          </p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div className="space-y-3">
        {/* Progress Bar */}
        <div>
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Progress</span>
            <span>
              {job['records_generated']} / {job['num_records']} records
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        </div>

        {/* Cost Tracking */}
        <div>
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Cost</span>
            <span>
              ${job['cost_estimate'].toFixed(2)} / ${job['budget_limit'].toFixed(2)}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                costProgress > 90 ? 'bg-orange-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(costProgress, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        <Link
          to={`/jobs/${job['job_id']}`}
          className="flex-1 text-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
        >
          View Details
        </Link>
        {job.status === 'COMPLETED' && (
          <button
            onClick={() => {
              // TODO: Implement download functionality
              // Should call API endpoint to download generated data for job['job_id']
            }}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm"
          >
            Download
          </button>
        )}
        {(job.status === 'RUNNING' || job.status === 'QUEUED') && (
          <button
            onClick={() => onDelete(job['job_id'])}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
          >
            Cancel
          </button>
        )}
        {(job.status === 'FAILED' || job.status === 'CANCELLED' || job.status === 'COMPLETED') && (
          <button
            onClick={() => onDelete(job['job_id'])}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors text-sm"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}
