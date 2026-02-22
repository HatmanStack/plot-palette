import { useQuery } from '@tanstack/react-query'
import { fetchTemplateVersions } from '../services/api'
import type { TemplateVersion } from '../services/api'

interface VersionListProps {
  templateId: string
  currentVersion: number
  onSelectVersion: (version: number) => void
  onCompare?: (version: number) => void
}

function formatRelativeDate(dateString: string): string {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function VersionList({ templateId, currentVersion, onSelectVersion, onCompare }: VersionListProps) {
  const { data: versions, isLoading, error } = useQuery({
    queryKey: ['template', templateId, 'versions'],
    queryFn: () => fetchTemplateVersions(templateId),
    enabled: !!templateId,
  })

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500 p-4">Loading versions...</div>
    )
  }

  if (error) {
    return (
      <div className="text-sm text-red-500 p-4">
        Failed to load versions: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    )
  }

  if (!versions || versions.length === 0) {
    return (
      <div className="text-sm text-gray-500 p-4">No versions found</div>
    )
  }

  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold text-gray-700 px-2 mb-2">Version History</h3>
      {versions.map((v: TemplateVersion) => (
        <div
          key={v.version}
          className={`flex items-center justify-between px-3 py-2 rounded cursor-pointer text-sm transition-colors ${
            v.version === currentVersion
              ? 'bg-blue-100 border border-blue-300'
              : 'hover:bg-gray-100'
          }`}
          onClick={() => onSelectVersion(v.version)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onSelectVersion(v.version)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium">v{v.version}</span>
              {v.version === currentVersion && (
                <span className="text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded">current</span>
              )}
            </div>
            {v.name && <div className="text-xs text-gray-500 truncate">{v.name}</div>}
            <div className="text-xs text-gray-400">{formatRelativeDate(v.created_at)}</div>
          </div>
          {onCompare && v.version !== currentVersion && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onCompare(v.version)
              }}
              className="ml-2 text-xs text-blue-600 hover:text-blue-800 whitespace-nowrap"
            >
              Compare
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
