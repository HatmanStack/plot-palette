import { Link } from 'react-router-dom'
import type { MarketplaceTemplate } from '../services/api'

interface Props {
  template: MarketplaceTemplate & { is_owner?: boolean }
  variant: 'owned' | 'marketplace'
  onFork?: () => void
  onDelete?: () => void
  onPreview?: () => void
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  if (days === 0) return 'today'
  if (days === 1) return '1 day ago'
  if (days < 30) return `${days} days ago`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 month ago' : `${months} months ago`
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

export default function TemplateCard({ template, variant, onFork, onDelete, onPreview }: Props) {
  return (
    <div className="bg-white rounded-lg shadow p-4 flex flex-col">
      <div className="flex-1">
        <h3 className="font-semibold text-gray-900 mb-1">{template.name}</h3>
        <p className="text-sm text-gray-500 mb-2">
          {truncate(template.description || 'No description', 100)}
        </p>
        <div className="flex flex-wrap gap-1 mb-2">
          {template.schema_requirements?.slice(0, 3).map((req) => (
            <span key={req} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {req}
            </span>
          ))}
        </div>
        <div className="text-xs text-gray-400 flex gap-3">
          <span>{template.step_count || 0} step{(template.step_count || 0) !== 1 ? 's' : ''}</span>
          <span>v{template.version}</span>
          {template.created_at && <span>{timeAgo(template.created_at)}</span>}
        </div>
      </div>

      <div className="flex gap-2 mt-3 pt-3 border-t">
        {variant === 'owned' ? (
          <>
            <Link
              to={`/templates/${template.template_id}`}
              className="flex-1 text-center px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Edit
            </Link>
            {onDelete && (
              <button
                onClick={onDelete}
                className="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 transition-colors"
              >
                Delete
              </button>
            )}
          </>
        ) : (
          <>
            {onPreview && (
              <button
                onClick={onPreview}
                className="flex-1 text-center px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
              >
                Preview
              </button>
            )}
            {onFork && (
              <button
                onClick={onFork}
                className="flex-1 text-center px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
              >
                Fork
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
