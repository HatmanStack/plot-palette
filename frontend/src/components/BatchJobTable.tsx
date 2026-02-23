import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { BatchJob } from '../services/api'

interface BatchJobTableProps {
  jobs: BatchJob[]
  sweepConfig: Record<string, unknown>
}

type SortKey = 'status' | 'records_generated' | 'cost_estimate'

export default function BatchJobTable({ jobs, sweepConfig }: BatchJobTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('status')
  const [sortAsc, setSortAsc] = useState(true)

  const sweepKey = Object.keys(sweepConfig)[0] || ''
  const sweepValues = (sweepConfig[sweepKey] as string[]) || []

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  const sorted = [...jobs].sort((a, b) => {
    const aVal = a[sortKey]
    const bVal = b[sortKey]
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortAsc ? aVal - bVal : bVal - aVal
    }
    return sortAsc
      ? String(aVal).localeCompare(String(bVal))
      : String(bVal).localeCompare(String(aVal))
  })

  const statusColor: Record<string, string> = {
    QUEUED: 'bg-gray-100 text-gray-800',
    RUNNING: 'bg-blue-100 text-blue-800',
    COMPLETED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
    CANCELLED: 'bg-yellow-100 text-yellow-800',
    BUDGET_EXCEEDED: 'bg-orange-100 text-orange-800',
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {sweepKey && <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sweep Value</th>}
            <th
              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer"
              onClick={() => handleSort('status')}
            >
              Status {sortKey === 'status' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th
              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer"
              onClick={() => handleSort('records_generated')}
            >
              Records {sortKey === 'records_generated' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th
              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer"
              onClick={() => handleSort('cost_estimate')}
            >
              Cost {sortKey === 'cost_estimate' ? (sortAsc ? '▲' : '▼') : ''}
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {sorted.map((job, index) => (
            <tr key={job.job_id}>
              {sweepKey && (
                <td className="px-4 py-3 text-sm font-medium text-gray-900">
                  {sweepValues[index] !== undefined ? String(sweepValues[index]) : '-'}
                </td>
              )}
              <td className="px-4 py-3">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor[job.status] || 'bg-gray-100'}`}>
                  {job.status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">{job.records_generated}</td>
              <td className="px-4 py-3 text-sm text-gray-700">${job.cost_estimate.toFixed(2)}</td>
              <td className="px-4 py-3 text-sm">
                <Link to={`/jobs/${job.job_id}`} className="text-blue-600 hover:underline">
                  View
                </Link>
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={sweepKey ? 5 : 4} className="px-4 py-8 text-center text-gray-500">
                No jobs in this batch
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
