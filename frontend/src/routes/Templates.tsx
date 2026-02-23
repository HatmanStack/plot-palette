import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '../hooks/useToast'
import {
  fetchUserTemplates,
  searchMarketplaceTemplates,
  forkTemplate,
  deleteTemplate,
} from '../services/api'
import type { Template, MarketplaceTemplate } from '../services/api'
import TemplateCard from '../components/TemplateCard'
import TemplatePreview from '../components/TemplatePreview'

type Tab = 'mine' | 'marketplace'

export default function Templates() {
  const [tab, setTab] = useState<Tab>('mine')
  const [searchQuery, setSearchQuery] = useState('')
  const [sort, setSort] = useState('recent')
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [lastKey, setLastKey] = useState<string | undefined>()

  const { toast } = useToast()
  const queryClient = useQueryClient()

  // My Templates query
  const {
    data: myTemplates,
    isLoading: myLoading,
    error: myError,
  } = useQuery({
    queryKey: ['templates', 'user'],
    queryFn: fetchUserTemplates,
    enabled: tab === 'mine',
  })

  // Marketplace query
  const {
    data: marketplaceData,
    isLoading: mpLoading,
    error: mpError,
  } = useQuery({
    queryKey: ['templates', 'marketplace', searchQuery, sort],
    queryFn: () => searchMarketplaceTemplates({ q: searchQuery || undefined, sort, limit: 20 }),
    enabled: tab === 'marketplace',
  })

  // Load more for marketplace
  const {
    data: moreData,
    isFetching: moreFetching,
  } = useQuery({
    queryKey: ['templates', 'marketplace', searchQuery, sort, 'more', lastKey],
    queryFn: () => searchMarketplaceTemplates({ q: searchQuery || undefined, sort, limit: 20, lastKey }),
    enabled: !!lastKey && tab === 'marketplace',
  })

  // Fork mutation
  const forkMutation = useMutation({
    mutationFn: (templateId: string) => forkTemplate(templateId),
    onSuccess: () => {
      toast('Template forked successfully', 'success')
      queryClient.invalidateQueries({ queryKey: ['templates', 'user'] })
      setPreviewId(null)
      setTab('mine')
    },
    onError: (err: Error) => {
      toast(err.message || 'Failed to fork template', 'error')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (templateId: string) => deleteTemplate(templateId),
    onSuccess: () => {
      toast('Template deleted', 'success')
      queryClient.invalidateQueries({ queryKey: ['templates', 'user'] })
    },
    onError: (err: Error) => {
      toast(err.message || 'Failed to delete template', 'error')
    },
  })

  const handleDelete = useCallback((templateId: string) => {
    if (confirm('Are you sure you want to delete this template?')) {
      deleteMutation.mutate(templateId)
    }
  }, [deleteMutation])

  const handleFork = useCallback((templateId: string) => {
    forkMutation.mutate(templateId)
  }, [forkMutation])

  const nextPageKey = marketplaceData?.last_key
  const handleLoadMore = useCallback(() => {
    if (nextPageKey) {
      setLastKey(nextPageKey)
    }
  }, [nextPageKey])

  // Combine initial + more marketplace results
  const marketplaceTemplates: MarketplaceTemplate[] = [
    ...(marketplaceData?.templates || []),
    ...(moreData?.templates || []),
  ]

  const isLoading = tab === 'mine' ? myLoading : mpLoading
  const error = tab === 'mine' ? myError : mpError

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Templates</h1>
        <Link
          to="/templates/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          + Create Template
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6 w-fit">
        <button
          onClick={() => setTab('mine')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'mine'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          My Templates
        </button>
        <button
          onClick={() => setTab('marketplace')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'marketplace'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Marketplace
        </button>
      </div>

      {/* Marketplace controls */}
      {tab === 'marketplace' && (
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-4 flex-wrap">
          <input
            type="text"
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setLastKey(undefined)
            }}
            className="flex-1 min-w-48 px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value)
              setLastKey(undefined)
            }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="recent">Recent</option>
            <option value="name">Name A-Z</option>
          </select>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <div className="text-xl text-gray-600">Loading templates...</div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
          Error: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {/* My Templates tab */}
      {!isLoading && !error && tab === 'mine' && (
        <>
          {(!myTemplates || myTemplates.length === 0) ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500 text-lg mb-4">No templates yet</p>
              <Link
                to="/templates/new"
                className="inline-block px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Create Your First Template
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {myTemplates.map((template: Template) => (
                <TemplateCard
                  key={template.template_id}
                  template={{
                    ...template,
                    step_count: template.steps?.length || 0,
                  }}
                  variant="owned"
                  onDelete={() => handleDelete(template.template_id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Marketplace tab */}
      {!isLoading && !error && tab === 'marketplace' && (
        <>
          {marketplaceTemplates.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500 text-lg">
                {searchQuery ? 'No templates match your search' : 'No public templates available'}
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {marketplaceTemplates.map((template) => (
                  <TemplateCard
                    key={template.template_id}
                    template={template}
                    variant="marketplace"
                    onFork={() => handleFork(template.template_id)}
                    onPreview={() => setPreviewId(template.template_id)}
                  />
                ))}
              </div>

              {nextPageKey && !lastKey && (
                <div className="text-center mt-6">
                  <button
                    onClick={handleLoadMore}
                    disabled={moreFetching}
                    className="px-6 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    {moreFetching ? 'Loading...' : 'Load More'}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Preview modal */}
      {previewId && (
        <TemplatePreview
          templateId={previewId}
          onClose={() => setPreviewId(null)}
          onFork={() => handleFork(previewId)}
        />
      )}
    </div>
  )
}
