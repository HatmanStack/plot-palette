import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchBatchDetail, deleteBatch } from '../services/api'
import { useToast } from '../hooks/useToast'
import BatchJobTable from '../components/BatchJobTable'
import { useState } from 'react'

const statusColors: Record<string, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-100 text-green-800',
  PARTIAL_FAILURE: 'bg-orange-100 text-orange-800',
}

export default function BatchDetail() {
  const { batchId } = useParams<{ batchId: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [showConfirm, setShowConfirm] = useState(false)

  const { data: batch, isLoading, error } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => fetchBatchDetail(batchId!),
    enabled: !!batchId,
    refetchInterval: (query) => {
      const d = query.state.data
      if (d && (d.status === 'RUNNING' || d.status === 'PENDING')) {
        return 5000
      }
      return false
    },
  })

  async function handleDelete() {
    if (!batchId) return
    try {
      await deleteBatch(batchId)
      queryClient.invalidateQueries({ queryKey: ['batches'] })
      toast('Batch deleted', 'success')
      navigate('/jobs')
    } catch {
      toast('Failed to delete batch', 'error')
    }
  }

  if (isLoading) return <div className="p-8">Loading batch...</div>
  if (error) return <div className="p-8 text-red-600">Error loading batch: {(error as Error).message}</div>
  if (!batch) return <div className="p-8">Batch not found</div>

  const progress = batch.total_jobs > 0
    ? Math.round(((batch.completed_jobs + batch.failed_jobs) / batch.total_jobs) * 100)
    : 0

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">{batch.name}</h1>
          <p className="text-gray-500 text-sm mt-1">
            Batch ID: {batch.batch_id} | Template: {batch.template_id} (v{batch.template_version})
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[batch.status] || 'bg-gray-100'}`}>
            {batch.status}
          </span>
          <button
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
          >
            Delete Batch
          </button>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-md mb-6">
          <p className="text-red-800 mb-3">
            This will cancel all running jobs and delete the batch. This action cannot be undone.
          </p>
          <div className="flex gap-2">
            <button onClick={handleDelete} className="px-4 py-2 bg-red-600 text-white rounded text-sm">
              Confirm Delete
            </button>
            <button onClick={() => setShowConfirm(false)} className="px-4 py-2 bg-gray-200 text-gray-800 rounded text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Progress */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            Progress: {batch.completed_jobs + batch.failed_jobs} of {batch.total_jobs} jobs complete
          </span>
          <span className="text-sm text-gray-500">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-blue-600 h-3 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex gap-6 mt-4 text-sm text-gray-600">
          <span>Completed: {batch.completed_jobs}</span>
          <span>Failed: {batch.failed_jobs}</span>
          <span>Total Cost: ${batch.total_cost.toFixed(2)}</span>
        </div>
      </div>

      {/* Job Comparison Table */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4">Job Comparison</h2>
        <BatchJobTable jobs={batch.jobs} sweepConfig={batch.sweep_config} />
      </div>
    </div>
  )
}
