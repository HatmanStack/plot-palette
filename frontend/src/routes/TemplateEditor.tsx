import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Editor from '@monaco-editor/react'

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

export default function TemplateEditor() {
  const { templateId } = useParams()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [templateYaml, setTemplateYaml] = useState(SAMPLE_TEMPLATE)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

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
      // For now, just simulate success
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
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">
          {templateId ? `Edit Template: ${templateId}` : 'New Template'}
        </h1>
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Template YAML
                </label>
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
                    }}
                  />
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  Write your template using YAML syntax with Jinja2 variables
                </p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={handleTest}
              className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
            >
              🧪 Test Template
            </button>
            <button
              onClick={handleSave}
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Saving...' : templateId ? '💾 Update' : '💾 Save'}
            </button>
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
            <p className="font-semibold">💡 Tip</p>
            <p className="mt-1">
              Use the "Test Template" button to validate your template syntax before saving.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
