import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Editor from '@monaco-editor/react'
import VersionList from '../components/VersionList'
import TemplateDiffView, { formatTemplateForDiff } from '../components/TemplateDiffView'
import { fetchTemplate } from '../services/api'
import type { Template } from '../services/api'

const SAMPLE_TEMPLATE = `template:
  id: creative-writing-v1
  name: "Creative Writing Story Generator"
  version: 1

  schema_requirements:
    - author.biography
    - poem.text
    - day.notes

  steps:
    - id: outline
      model: llama-3.1-8b
      prompt: |
        Generate a story outline using:
        Author: {{ author.name }}
        Theme: {{ poem.text[:100] }}
        Setting: {{ day.notes | random_sentence }}

    - id: expand
      model: claude-sonnet
      prompt: |
        Expand this outline into a full story:
        {{ steps.outline.output }}

        Use {{ author.biography | writing_style }} style.`

function formatTemplateAsYaml(template: Template): string {
  let yaml = `template:\n`
  yaml += `  name: "${template.name}"\n`
  yaml += `  version: ${template.version}\n\n`

  if (template.schema_requirements.length > 0) {
    yaml += `  schema_requirements:\n`
    for (const req of template.schema_requirements) {
      yaml += `    - ${req}\n`
    }
    yaml += `\n`
  }

  if (template.steps.length > 0) {
    yaml += `  steps:\n`
    for (const step of template.steps) {
      yaml += `    - id: ${step.id}\n`
      yaml += `      model: ${step.model || step.model_tier || 'default'}\n`
      yaml += `      prompt: |\n`
      for (const line of step.prompt.split('\n')) {
        yaml += `        ${line}\n`
      }
      yaml += `\n`
    }
  }

  return yaml
}

export default function TemplateEditor() {
  const { templateId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [templateYaml, setTemplateYaml] = useState(SAMPLE_TEMPLATE)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  // Version state
  const [currentVersion, setCurrentVersion] = useState(1)
  const [latestVersion, setLatestVersion] = useState(1)
  const [showVersionSidebar, setShowVersionSidebar] = useState(true)

  // Diff mode state
  const [diffMode, setDiffMode] = useState(false)
  const [diffCompareVersion, setDiffCompareVersion] = useState<number | null>(null)

  // Fetch template data when editing existing template
  const { data: templateData } = useQuery({
    queryKey: ['template', templateId, currentVersion],
    queryFn: () => fetchTemplate(templateId!, currentVersion),
    enabled: !!templateId,
  })

  // Initialize from fetched template data
  useEffect(() => {
    if (templateData) {
      setName(templateData.name)
      setDescription(templateData.description)
      setTemplateYaml(formatTemplateAsYaml(templateData))
      if (currentVersion === 1 && templateData.version > 1) {
        // On initial load, set both current and latest to the fetched version
        setCurrentVersion(templateData.version)
        setLatestVersion(templateData.version)
      }
    }
  }, [templateData, currentVersion])

  // Fetch latest version on mount to determine the latest
  const { data: latestTemplateData } = useQuery({
    queryKey: ['template', templateId, 'latest-ref'],
    queryFn: () => fetchTemplate(templateId!, 'latest'),
    enabled: !!templateId,
  })

  useEffect(() => {
    if (latestTemplateData) {
      setLatestVersion(latestTemplateData.version)
      // Set current to latest on first load
      if (currentVersion === 1 && latestTemplateData.version > 1) {
        setCurrentVersion(latestTemplateData.version)
      }
    }
  }, [latestTemplateData, currentVersion])

  // Fetch comparison version for diff mode
  const { data: compareTemplateData } = useQuery({
    queryKey: ['template', templateId, diffCompareVersion],
    queryFn: () => fetchTemplate(templateId!, diffCompareVersion!),
    enabled: !!templateId && diffMode && diffCompareVersion !== null,
  })

  const isViewingHistorical = templateId && currentVersion < latestVersion

  function handleSelectVersion(version: number) {
    setDiffMode(false)
    setDiffCompareVersion(null)
    setCurrentVersion(version)
    queryClient.invalidateQueries({ queryKey: ['template', templateId, version] })
  }

  function handleCompare(version: number) {
    setDiffCompareVersion(version)
    setDiffMode(true)
  }

  function handleExitDiff() {
    setDiffMode(false)
    setDiffCompareVersion(null)
  }

  async function handleRestore() {
    if (!templateId || !templateData) return
    setLoading(true)
    setError('')
    try {
      // TODO: call update API to create new version from current view
      await new Promise((resolve) => setTimeout(resolve, 500))
      setSuccess('Version restored as new version')
      const newVersion = latestVersion + 1
      setCurrentVersion(newVersion)
      setLatestVersion(newVersion)
      queryClient.invalidateQueries({ queryKey: ['template', templateId, 'versions'] })
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restore version')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!name || !templateYaml) {
      setError('Please provide both a name and template content')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      // TODO: Implement actual API call to save template
      await new Promise((resolve) => setTimeout(resolve, 1000))

      setSuccess('Template saved successfully!')
      setTimeout(() => {
        navigate('/templates')
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save template')
    } finally {
      setLoading(false)
    }
  }

  async function handleTest() {
    setError('')
    setSuccess('Template test not implemented yet — this is a placeholder')
    setTimeout(() => setSuccess(''), 3000)
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">
            {templateId ? `Edit Template: ${templateId}` : 'New Template'}
          </h1>
          {isViewingHistorical && (
            <p className="text-sm text-amber-600 mt-1">
              Viewing version {currentVersion} (read-only) — Latest is v{latestVersion}
            </p>
          )}
        </div>
        <Link
          to="/templates"
          className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
        >
          ← Back to Templates
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-600 px-4 py-3 rounded mb-4">
          {success}
        </div>
      )}

      <div className={`grid gap-6 ${templateId ? 'grid-cols-1 lg:grid-cols-[1fr_1fr_250px]' : 'grid-cols-1 lg:grid-cols-2'}`}>
        {/* Editor Section */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Template Details</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Template Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Creative Writing Generator"
                  disabled={!!isViewingHistorical}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of what this template does"
                  rows={3}
                  disabled={!!isViewingHistorical}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {diffMode ? 'Diff View' : 'Template YAML'}
                </label>
                {diffMode && templateData && compareTemplateData ? (
                  <div>
                    <TemplateDiffView
                      originalContent={formatTemplateForDiff(compareTemplateData)}
                      modifiedContent={formatTemplateForDiff(templateData)}
                      originalVersion={diffCompareVersion!}
                      modifiedVersion={currentVersion}
                    />
                    <button
                      onClick={handleExitDiff}
                      className="mt-2 text-sm text-blue-600 hover:text-blue-800"
                    >
                      Exit Diff View
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="border border-gray-300 rounded-md overflow-hidden">
                      <Editor
                        height="500px"
                        defaultLanguage="yaml"
                        value={templateYaml}
                        onChange={(value) => setTemplateYaml(value || '')}
                        theme="vs-light"
                        options={{
                          minimap: { enabled: false },
                          fontSize: 13,
                          lineNumbers: 'on',
                          scrollBeyondLastLine: false,
                          automaticLayout: true,
                          tabSize: 2,
                          wordWrap: 'on',
                          readOnly: !!isViewingHistorical,
                        }}
                      />
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {isViewingHistorical
                        ? 'Read-only: viewing a historical version'
                        : 'Write your template using YAML syntax with Jinja2 variables'}
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            {isViewingHistorical ? (
              <button
                onClick={handleRestore}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50 transition-colors"
              >
                {loading ? 'Restoring...' : 'Restore This Version'}
              </button>
            ) : (
              <>
                <button
                  onClick={handleTest}
                  className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
                >
                  Test Template
                </button>
                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Saving...' : templateId ? 'Update' : 'Save'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Preview/Help Section */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Template Help</h2>

            <div className="space-y-4 text-sm">
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Basic Structure</h3>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
{`template:
  id: my-template
  name: "Template Name"
  version: 1`}
                </pre>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Using Variables</h3>
                <p className="text-gray-600 mb-2">
                  Use Jinja2 syntax to reference seed data:
                </p>
                <code className="bg-gray-50 px-2 py-1 rounded">
                  {'{{ author.name }}'}, {'{{ poem.text }}'}
                </code>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Custom Filters</h3>
                <ul className="list-disc list-inside text-gray-600 space-y-1">
                  <li>
                    <code>random_sentence</code> - Extract random sentence
                  </li>
                  <li>
                    <code>writing_style</code> - Extract writing style
                  </li>
                  <li>
                    <code>truncate_tokens</code> - Truncate to N tokens
                  </li>
                </ul>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Multi-Step</h3>
                <p className="text-gray-600 mb-2">
                  Reference previous step outputs:
                </p>
                <code className="bg-gray-50 px-2 py-1 rounded">
                  {'{{ steps.outline.output }}'}
                </code>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Conditionals</h3>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
{`{% if author.genre == "poetry" %}
  Generate in verse
{% else %}
  Generate in prose
{% endif %}`}
                </pre>
              </div>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded text-sm">
            <p className="font-semibold">Tip</p>
            <p className="mt-1">
              Use the "Test Template" button to validate your template syntax before saving.
            </p>
          </div>
        </div>

        {/* Version History Sidebar — only for existing templates */}
        {templateId && showVersionSidebar && (
          <div className="space-y-4">
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-700">Versions</h2>
                <button
                  onClick={() => setShowVersionSidebar(false)}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  Hide
                </button>
              </div>
              <VersionList
                templateId={templateId}
                currentVersion={currentVersion}
                onSelectVersion={handleSelectVersion}
                onCompare={handleCompare}
              />
            </div>
          </div>
        )}

        {templateId && !showVersionSidebar && (
          <div>
            <button
              onClick={() => setShowVersionSidebar(true)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Show Version History
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
