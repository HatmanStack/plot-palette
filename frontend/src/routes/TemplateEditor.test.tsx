import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '../test/test-utils'
import TemplateEditor from './TemplateEditor'

// Mock Monaco editor
vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange, options }: { value: string; onChange: (v: string) => void; options?: { readOnly?: boolean } }) => (
    <textarea
      data-testid="monaco-editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      readOnly={options?.readOnly}
      aria-readonly={options?.readOnly}
    />
  ),
}))

// Mock API functions
vi.mock('../services/api', () => ({
  fetchTemplate: vi.fn(),
  fetchTemplateVersions: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({}),
  }
})

describe('TemplateEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders new template form', () => {
    render(<TemplateEditor />)
    expect(screen.getByText('New Template')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g., Creative Writing Generator')).toBeInTheDocument()
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()
    expect(screen.getByText('Template Help')).toBeInTheDocument()
  })

  it('has back link to templates', () => {
    render(<TemplateEditor />)
    expect(screen.getByText(/Back to Templates/)).toHaveAttribute('href', '/templates')
  })

  it('shows validation error when saving without a name', () => {
    render(<TemplateEditor />)
    fireEvent.click(screen.getByRole('button', { name: /Save/ }))
    expect(screen.getByText('Please provide both a name and template content')).toBeInTheDocument()
  })

  it('saves template and navigates on success', async () => {
    vi.useFakeTimers()
    render(<TemplateEditor />)

    fireEvent.change(screen.getByPlaceholderText('e.g., Creative Writing Generator'), {
      target: { value: 'My Template' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Save/ }))

    // Advance past the simulated save delay
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })

    expect(screen.getByText('Template saved successfully!')).toBeInTheDocument()

    // Advance past the navigate timeout
    act(() => {
      vi.advanceTimersByTime(1500)
    })

    expect(mockNavigate).toHaveBeenCalledWith('/templates')
    vi.useRealTimers()
  })

  it('shows placeholder message on test button click', async () => {
    vi.useFakeTimers()
    render(<TemplateEditor />)
    fireEvent.click(screen.getByRole('button', { name: /Test Template/ }))

    expect(screen.getByText(/Template test not implemented yet/)).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(screen.queryByText(/Template test not implemented yet/)).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('shows help content sections', () => {
    render(<TemplateEditor />)
    expect(screen.getByText('Basic Structure')).toBeInTheDocument()
    expect(screen.getByText('Using Variables')).toBeInTheDocument()
    expect(screen.getByText('Custom Filters')).toBeInTheDocument()
    expect(screen.getByText('Multi-Step')).toBeInTheDocument()
    expect(screen.getByText('Conditionals')).toBeInTheDocument()
  })

  it('hides version sidebar for new template', () => {
    render(<TemplateEditor />)
    // Version sidebar should not be present
    expect(screen.queryByText('Versions')).not.toBeInTheDocument()
    expect(screen.queryByText('Version History')).not.toBeInTheDocument()
  })
})

describe('TemplateEditor in edit mode', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const routerModule = await import('react-router-dom')
    vi.spyOn(routerModule, 'useParams').mockReturnValue({
      templateId: 'tmpl-abc123',
    })

    const apiModule = await import('../services/api')
    vi.mocked(apiModule.fetchTemplate).mockResolvedValue({
      template_id: 'tmpl-abc123',
      version: 2,
      name: 'Test Template',
      description: 'A test',
      user_id: 'user-1',
      is_public: false,
      is_owner: true,
      created_at: '2025-01-01T00:00:00',
      steps: [{ id: 'step1', prompt: 'Generate something' }],
      schema_requirements: ['author.name'],
    })
    vi.mocked(apiModule.fetchTemplateVersions).mockResolvedValue([
      { version: 2, name: 'v2', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: 'v1', description: '', created_at: '2025-01-01T00:00:00' },
    ])
  })

  it('renders edit mode when templateId is present', async () => {
    render(<TemplateEditor />)
    expect(screen.getByText(/Edit Template: tmpl-abc123/)).toBeInTheDocument()
  })

  it('shows version sidebar when editing existing template', async () => {
    render(<TemplateEditor />)

    await waitFor(() => {
      expect(screen.getByText('Versions')).toBeInTheDocument()
    })
  })
})
