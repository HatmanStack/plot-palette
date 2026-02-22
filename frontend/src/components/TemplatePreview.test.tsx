import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../test/test-utils'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchTemplate: vi.fn(),
  }
})

import { fetchTemplate } from '../services/api'
import TemplatePreview from './TemplatePreview'

const mockTemplate = {
  template_id: 'tmpl-1',
  version: 2,
  name: 'Poetry Generator',
  description: 'Creates poetry datasets',
  user_id: 'user-1',
  is_public: true,
  is_owner: false,
  created_at: '2026-02-20T00:00:00Z',
  steps: [
    { id: 'question', prompt: 'Generate a question about {{ author.name }}', model_tier: 'tier-1' },
    { id: 'answer', prompt: 'Answer: {{ steps.question.output }}', model_tier: 'tier-3' },
  ],
  schema_requirements: ['author.name', 'author.bio'],
}

describe('TemplatePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches and renders template details', async () => {
    vi.mocked(fetchTemplate).mockResolvedValueOnce(mockTemplate)

    render(
      <TemplatePreview templateId="tmpl-1" onClose={vi.fn()} onFork={vi.fn()} />,
      { withRouter: false },
    )

    await waitFor(() => {
      expect(screen.getByText('Poetry Generator')).toBeInTheDocument()
    })

    expect(screen.getByText('Creates poetry datasets')).toBeInTheDocument()
  })

  it('shows all template steps', async () => {
    vi.mocked(fetchTemplate).mockResolvedValueOnce(mockTemplate)

    render(
      <TemplatePreview templateId="tmpl-1" onClose={vi.fn()} onFork={vi.fn()} />,
      { withRouter: false },
    )

    await waitFor(() => {
      expect(screen.getByText('Steps (2)')).toBeInTheDocument()
    })

    expect(screen.getByText(/Step 1: question/)).toBeInTheDocument()
    expect(screen.getByText(/Step 2: answer/)).toBeInTheDocument()
  })

  it('calls onFork when Fork button clicked', async () => {
    vi.mocked(fetchTemplate).mockResolvedValueOnce(mockTemplate)
    const onFork = vi.fn()

    render(
      <TemplatePreview templateId="tmpl-1" onClose={vi.fn()} onFork={onFork} />,
      { withRouter: false },
    )

    await waitFor(() => {
      expect(screen.getByText('Poetry Generator')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Fork Template'))
    expect(onFork).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when close button clicked', async () => {
    vi.mocked(fetchTemplate).mockResolvedValueOnce(mockTemplate)
    const onClose = vi.fn()

    render(
      <TemplatePreview templateId="tmpl-1" onClose={onClose} onFork={vi.fn()} />,
      { withRouter: false },
    )

    await waitFor(() => {
      expect(screen.getByText('Poetry Generator')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
