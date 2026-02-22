import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TemplateDiffView, { formatTemplateForDiff } from './TemplateDiffView'
import type { Template } from '../services/api'

// Mock Monaco DiffEditor
vi.mock('@monaco-editor/react', () => ({
  default: (props: { value: string }) => <div data-testid="monaco-editor">{props.value}</div>,
  DiffEditor: (props: { original: string; modified: string; options?: { readOnly?: boolean } }) => (
    <div data-testid="monaco-diff-editor" data-readonly={props.options?.readOnly}>
      <div data-testid="original">{props.original}</div>
      <div data-testid="modified">{props.modified}</div>
    </div>
  ),
}))

describe('TemplateDiffView', () => {
  it('renders DiffEditor with provided content', () => {
    render(
      <TemplateDiffView
        originalContent="original text"
        modifiedContent="modified text"
        originalVersion={1}
        modifiedVersion={2}
      />
    )

    expect(screen.getByTestId('monaco-diff-editor')).toBeInTheDocument()
    expect(screen.getByTestId('original')).toHaveTextContent('original text')
    expect(screen.getByTestId('modified')).toHaveTextContent('modified text')
  })

  it('shows version numbers in header', () => {
    render(
      <TemplateDiffView
        originalContent=""
        modifiedContent=""
        originalVersion={1}
        modifiedVersion={3}
      />
    )

    expect(screen.getByText('Version 1 vs Version 3')).toBeInTheDocument()
  })

  it('DiffEditor is read-only', () => {
    render(
      <TemplateDiffView
        originalContent=""
        modifiedContent=""
        originalVersion={1}
        modifiedVersion={2}
      />
    )

    const diffEditor = screen.getByTestId('monaco-diff-editor')
    expect(diffEditor).toHaveAttribute('data-readonly', 'true')
  })
})

describe('formatTemplateForDiff', () => {
  it('formats template steps into readable text', () => {
    const template: Template = {
      template_id: 'tmpl-1',
      version: 1,
      name: 'Test Template',
      description: 'A test template',
      user_id: 'user-1',
      is_public: false,
      is_owner: true,
      created_at: '2025-01-01',
      steps: [
        { id: 'step1', model: 'llama-8b', prompt: 'Generate something about {{ name }}' },
        { id: 'step2', model: 'claude-sonnet', prompt: 'Expand: {{ steps.step1.output }}' },
      ],
      schema_requirements: ['name', 'bio'],
    }

    const result = formatTemplateForDiff(template)

    expect(result).toContain('# Template: Test Template')
    expect(result).toContain('# Version: 1')
    expect(result).toContain('# Step: step1')
    expect(result).toContain('Model: llama-8b')
    expect(result).toContain('Generate something about {{ name }}')
    expect(result).toContain('# Step: step2')
    expect(result).toContain('- name')
    expect(result).toContain('- bio')
  })
})
