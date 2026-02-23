import { useState } from 'react'
import type { CostAnalytics } from '../services/api'

interface Props {
  timeSeries: CostAnalytics['time_series']
}

function formatDate(dateStr: string): string {
  if (dateStr.includes('W')) return dateStr // Week format
  const parts = dateStr.split('-')
  if (parts.length >= 3) return `${parts[1]}/${parts[2]}`
  return dateStr
}

export default function CostChart({ timeSeries }: Props) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  if (timeSeries.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        No cost data for this period
      </div>
    )
  }

  const maxTotal = Math.max(...timeSeries.map((d) => d.total), 0.01)

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Spend Over Time</h3>
      <div className="flex items-end gap-1" style={{ height: '200px' }}>
        {timeSeries.map((entry, idx) => {
          const heightPct = (entry.total / maxTotal) * 100
          const bedrockPct = entry.total > 0 ? (entry.bedrock / entry.total) * heightPct : 0
          const fargatePct = entry.total > 0 ? (entry.fargate / entry.total) * heightPct : 0
          const s3Pct = entry.total > 0 ? (entry.s3 / entry.total) * heightPct : 0

          return (
            <div
              key={entry.date}
              className="flex-1 flex flex-col justify-end relative cursor-pointer"
              style={{ height: '100%' }}
              onMouseEnter={() => setHoveredIndex(idx)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {hoveredIndex === idx && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
                  <div>{entry.date}</div>
                  <div>Bedrock: ${entry.bedrock.toFixed(2)}</div>
                  <div>Fargate: ${entry.fargate.toFixed(2)}</div>
                  <div>S3: ${entry.s3.toFixed(2)}</div>
                  <div className="font-bold">Total: ${entry.total.toFixed(2)}</div>
                </div>
              )}
              <div className="w-full flex flex-col justify-end" style={{ height: `${heightPct}%` }}>
                <div
                  className="w-full bg-blue-500 rounded-t-sm"
                  style={{ height: `${bedrockPct > 0 ? Math.max(bedrockPct / heightPct * 100, 2) : 0}%` }}
                  title={`Bedrock: $${entry.bedrock.toFixed(2)}`}
                />
                <div
                  className="w-full bg-green-500"
                  style={{ height: `${fargatePct > 0 ? Math.max(fargatePct / heightPct * 100, 2) : 0}%` }}
                  title={`Fargate: $${entry.fargate.toFixed(2)}`}
                />
                <div
                  className="w-full bg-gray-400 rounded-b-sm"
                  style={{ height: `${s3Pct > 0 ? Math.max(s3Pct / heightPct * 100, 2) : 0}%` }}
                  title={`S3: $${entry.s3.toFixed(2)}`}
                />
              </div>
              <div className="text-xs text-gray-500 text-center mt-1 truncate">
                {formatDate(entry.date)}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-3 text-xs text-gray-600">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-blue-500 rounded-sm inline-block" /> Bedrock
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-green-500 rounded-sm inline-block" /> Fargate
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-gray-400 rounded-sm inline-block" /> S3
        </span>
      </div>
    </div>
  )
}
