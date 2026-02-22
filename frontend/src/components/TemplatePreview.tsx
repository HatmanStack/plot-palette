import { useQuery } from '@tanstack/react-query'
import { fetchTemplate } from '../services/api'

interface Props {
  templateId: string
  onClose: () => void
  onFork: () => void
}

export default function TemplatePreview({ templateId, onClose, onFork }: Props) {
  const { data: template, isLoading, error } = useQuery({
    queryKey: ['template', templateId, 'preview'],
    queryFn: () => fetchTemplate(templateId, 'latest'),
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
         onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              {isLoading ? 'Loading...' : template?.name || 'Template Preview'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            >
              x
            </button>
          </div>

          {isLoading && (
            <div className="space-y-3 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4" />
              <div className="h-4 bg-gray-200 rounded w-1/2" />
              <div className="h-20 bg-gray-200 rounded" />
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
              Error loading template: {error instanceof Error ? error.message : 'Unknown error'}
            </div>
          )}

          {template && (
            <div className="space-y-4">
              {template.description && (
                <p className="text-gray-600">{template.description}</p>
              )}

              {template.schema_requirements.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-1">Schema Requirements</h3>
                  <div className="flex flex-wrap gap-1">
                    {template.schema_requirements.map((req) => (
                      <span key={req} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                        {req}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  Steps ({template.steps.length})
                </h3>
                <div className="space-y-3">
                  {template.steps.map((step, idx) => (
                    <div key={step.id} className="border rounded p-3">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm font-medium text-gray-900">
                          Step {idx + 1}: {step.id}
                        </span>
                        <span className="text-xs text-gray-500">
                          {step.model_tier || step.model || 'default'}
                        </span>
                      </div>
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto whitespace-pre-wrap">
                        {step.prompt}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
            >
              Close
            </button>
            <button
              onClick={onFork}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              Fork Template
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
