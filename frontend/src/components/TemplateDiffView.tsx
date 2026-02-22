import { DiffEditor } from '@monaco-editor/react'
import type { Template } from '../services/api'

interface TemplateDiffViewProps {
  originalContent: string
  modifiedContent: string
  originalVersion: number
  modifiedVersion: number
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatTemplateForDiff(template: Template): string {
  const lines: string[] = []

  lines.push(`# Template: ${template.name}`)
  lines.push(`# Version: ${template.version}`)
  if (template.description) {
    lines.push(`# Description: ${template.description}`)
  }
  lines.push('')

  if (template.schema_requirements.length > 0) {
    lines.push('# Schema Requirements')
    for (const req of template.schema_requirements) {
      lines.push(`- ${req}`)
    }
    lines.push('')
  }

  for (const step of template.steps) {
    lines.push(`# Step: ${step.id}`)
    lines.push(`Model: ${step.model || step.model_tier || 'default'}`)
    lines.push('')
    lines.push(step.prompt)
    lines.push('')
    lines.push('---')
    lines.push('')
  }

  return lines.join('\n')
}

export default function TemplateDiffView({
  originalContent,
  modifiedContent,
  originalVersion,
  modifiedVersion,
}: TemplateDiffViewProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">
          Version {originalVersion} vs Version {modifiedVersion}
        </span>
      </div>
      <div className="border border-gray-300 rounded-md overflow-hidden">
        <DiffEditor
          height="500px"
          language="yaml"
          original={originalContent}
          modified={modifiedContent}
          options={{
            readOnly: true,
            renderSideBySide: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            fontSize: 13,
          }}
        />
      </div>
    </div>
  )
}
