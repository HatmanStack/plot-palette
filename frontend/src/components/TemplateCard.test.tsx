import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '../test/test-utils'
import TemplateCard from './TemplateCard'

const mockTemplate = {
  template_id: 'tmpl-1',
  name: 'Poetry Generator',
  description: 'Generates poetry using author data and creative prompts for training',
  user_id: 'user-1',
  version: 2,
  schema_requirements: ['author.name', 'author.bio'],
  step_count: 3,
  created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
}

describe('TemplateCard', () => {
  it('renders template name and description', () => {
    render(
      <TemplateCard template={mockTemplate} variant="owned" />,
    )

    expect(screen.getByText('Poetry Generator')).toBeInTheDocument()
    expect(screen.getByText(/Generates poetry/)).toBeInTheDocument()
  })

  it('owned variant shows Edit and Delete buttons', () => {
    const onDelete = vi.fn()
    render(
      <TemplateCard template={mockTemplate} variant="owned" onDelete={onDelete} />,
    )

    expect(screen.getByText('Edit')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('marketplace variant shows Preview and Fork buttons', () => {
    const onFork = vi.fn()
    const onPreview = vi.fn()
    render(
      <TemplateCard template={mockTemplate} variant="marketplace" onFork={onFork} onPreview={onPreview} />,
    )

    expect(screen.getByText('Preview')).toBeInTheDocument()
    expect(screen.getByText('Fork')).toBeInTheDocument()
  })

  it('calls onFork when Fork clicked', () => {
    const onFork = vi.fn()
    render(
      <TemplateCard template={mockTemplate} variant="marketplace" onFork={onFork} />,
    )

    fireEvent.click(screen.getByText('Fork'))
    expect(onFork).toHaveBeenCalledTimes(1)
  })

  it('truncates long descriptions', () => {
    const longDesc = 'A'.repeat(200)
    render(
      <TemplateCard template={{ ...mockTemplate, description: longDesc }} variant="owned" />,
    )

    const desc = screen.getByText(/A+\.\.\./)
    expect(desc).toBeInTheDocument()
  })
})
