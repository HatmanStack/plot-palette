import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCostAnalytics } from '../services/api'
import CostSummaryCards from '../components/CostSummaryCards'
import CostChart from '../components/CostChart'
import ModelCostBreakdown from '../components/ModelCostBreakdown'

type Period = '7d' | '30d' | '90d'

export default function CostAnalytics() {
  const [period, setPeriod] = useState<Period>('30d')

  const { data, isLoading, error } = useQuery({
    queryKey: ['costs', 'analytics', period],
    queryFn: () => fetchCostAnalytics(period, 'day'),
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-bold text-gray-900">Cost Analytics</h1>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-lg shadow p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-20 mb-2" />
              <div className="h-8 bg-gray-200 rounded w-24" />
            </div>
          ))}
        </div>
        <div className="bg-white rounded-lg shadow p-4 animate-pulse" style={{ height: '248px' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Cost Analytics</h1>
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
          Error loading cost data: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Cost Analytics</h1>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {(['7d', '30d', '90d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                period === p
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {p === '7d' ? '7 Days' : p === '30d' ? '30 Days' : '90 Days'}
            </button>
          ))}
        </div>
      </div>

      <CostSummaryCards summary={data.summary} />
      <CostChart timeSeries={data.time_series} />
      <ModelCostBreakdown byModel={data.by_model} />
    </div>
  )
}
