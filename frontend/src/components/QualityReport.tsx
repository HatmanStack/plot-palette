import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchQualityMetrics, triggerQualityScoring } from '../services/api'
import type { QualityMetrics } from '../services/api'
import { useToast } from '../hooks/useToast'
import QualityScoreBar from './QualityScoreBar'

interface QualityReportProps {
  jobId: string
}

export default function QualityReport({ jobId }: QualityReportProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [showDetails, setShowDetails] = useState(false)

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['quality', jobId],
    queryFn: () => fetchQualityMetrics(jobId),
    refetchInterval: (query) => {
      const d = query.state.data
      if (d && d.status === 'SCORING') return 5000
      return false
    },
  })

  const scoreMutation = useMutation({
    mutationFn: () => triggerQualityScoring(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quality', jobId] })
      toast('Quality scoring started', 'success')
    },
    onError: () => {
      toast('Failed to start quality scoring', 'error')
    },
  })

  if (isLoading) {
    return <div className="text-gray-500 text-sm">Loading quality data...</div>
  }

  // Not scored yet
  if (!metrics) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4">Quality Score</h2>
        <p className="text-gray-500 mb-4">No quality assessment has been run for this job.</p>
        <button
          onClick={() => scoreMutation.mutate()}
          disabled={scoreMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {scoreMutation.isPending ? 'Starting...' : 'Run Quality Check'}
        </button>
      </div>
    )
  }

  // Scoring in progress
  if (metrics.status === 'SCORING' || metrics.status === 'PENDING') {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4">Quality Score</h2>
        <div className="flex items-center gap-3">
          <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
          <span className="text-gray-600">Scoring in progress (this may take a minute)...</span>
        </div>
      </div>
    )
  }

  // Failed
  if (metrics.status === 'FAILED') {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4">Quality Score</h2>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          Scoring failed: {metrics.error_message || 'Unknown error'}
        </div>
        <button
          onClick={() => scoreMutation.mutate()}
          disabled={scoreMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {scoreMutation.isPending ? 'Retrying...' : 'Retry'}
        </button>
      </div>
    )
  }

  // Completed — full report
  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold mb-4">Quality Score</h2>

      {/* Overall Score */}
      <div className="mb-6">
        <QualityScoreBar score={metrics.overall_score} label="Overall Score" />
      </div>

      {/* Dimension Breakdown */}
      <div className="space-y-3 mb-6">
        <h3 className="text-sm font-medium text-gray-500 uppercase">Dimensions</h3>
        {metrics.aggregate_scores.coherence !== undefined && (
          <QualityScoreBar score={metrics.aggregate_scores.coherence} label="Coherence" />
        )}
        {metrics.aggregate_scores.relevance !== undefined && (
          <QualityScoreBar score={metrics.aggregate_scores.relevance} label="Relevance" />
        )}
        {metrics.aggregate_scores.format_compliance !== undefined && (
          <QualityScoreBar score={metrics.aggregate_scores.format_compliance} label="Format Compliance" />
        )}
        <QualityScoreBar score={metrics.diversity_score} label="Diversity" />
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-4">
        <div>
          <span className="text-gray-500">Sample Size:</span>{' '}
          {metrics.sample_size} of {metrics.total_records}
        </div>
        <div>
          <span className="text-gray-500">Scoring Cost:</span>{' '}
          ${metrics.scoring_cost.toFixed(4)}
        </div>
        <div>
          <span className="text-gray-500">Model:</span>{' '}
          {metrics.model_used_for_scoring.split('.').pop()?.split('-v')[0] || metrics.model_used_for_scoring}
        </div>
        <div>
          <span className="text-gray-500">Scored At:</span>{' '}
          {new Date(metrics.scored_at).toLocaleString()}
        </div>
      </div>

      {/* Per-Record Details (expandable) */}
      {metrics.record_scores.length > 0 && (
        <div>
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {showDetails ? 'Hide' : 'Show'} per-record scores ({metrics.record_scores.length} records)
          </button>

          {showDetails && (
            <div className="mt-3 max-h-64 overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Record</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Coherence</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Relevance</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Format</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {metrics.record_scores.map((rs) => (
                    <tr key={rs.record_index}>
                      <td className="px-3 py-2 text-gray-700">#{rs.record_index + 1}</td>
                      <td className="px-3 py-2">{rs.coherence.toFixed(2)}</td>
                      <td className="px-3 py-2">{rs.relevance.toFixed(2)}</td>
                      <td className="px-3 py-2">{rs.format_compliance.toFixed(2)}</td>
                      <td className="px-3 py-2 text-gray-500 truncate max-w-[200px]">{rs.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
