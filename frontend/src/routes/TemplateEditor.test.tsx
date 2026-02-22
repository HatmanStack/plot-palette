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

// Mock API functions — names match the actual export
const mockUpdateTemplate = vi.fn()
const mockCreateTemplate = vi.fn()
vi.mock('../services/api', () => ({
  fetchTemplate: vi.fn(),
  fetchTemplateVersions: vi.fn(),
  updateTemplate: (...args: unknown[]) => mockUpdateTemplate(...args),
  createTemplate: (...args: unknown[]) => mockCreateTemplate(...args),
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

  it('saves template via API and navigates on success', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockCreateTemplate.mockResolvedValueOnce({
      template_id: 'new-tmpl-123',
      version: 1,
      name: 'My Template',
    })

    render(<TemplateEditor />)

    fireEvent.change(screen.getByPlaceholderText('e.g., Creative Writing Generator'), {
      target: { value: 'My Template' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Save/ }))

    await waitFor(() => {
      expect(screen.getByText('Template saved successfully!')).toBeInTheDocument()
    })

    expect(mockCreateTemplate).toHaveBeenCalled()

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
      { version: 2, name: 'Updated', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: 'Initial', description: '', created_at: '2025-01-01T00:00:00' },
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

  it('switches to read-only when viewing historical version', async () => {
    // Set up so latestVersion=3, currentVersion starts at 3
    const apiModule = await import('../services/api')
    vi.mocked(apiModule.fetchTemplate).mockImplementation((_id, version) => {
      const v = version === 'latest' ? 3 : (typeof version === 'number' ? version : 1)
      return Promise.resolve({
        template_id: 'tmpl-abc123',
        version: v,
        name: `Template v${v}`,
        description: '',
        user_id: 'user-1',
        is_public: false,
        is_owner: true,
        created_at: '2025-01-01T00:00:00',
        steps: [{ id: 'step1', prompt: 'content' }],
        schema_requirements: [],
      })
    })
    // Use distinct names that don't clash with the "v{N}" version label
    vi.mocked(apiModule.fetchTemplateVersions).mockResolvedValue([
      { version: 3, name: 'Third', description: '', created_at: '2025-01-03T00:00:00' },
      { version: 2, name: 'Second', description: '', created_at: '2025-01-02T00:00:00' },
      { version: 1, name: 'First', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    render(<TemplateEditor />)

    // Wait for version list to load — use the unique name text
    await waitFor(() => {
      expect(screen.getByText('First')).toBeInTheDocument()
    })

    // Click on version 1's name to select it
    fireEvent.click(screen.getByText('First'))

    // Wait for the editor to become read-only
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor')
      expect(editor).toHaveAttribute('aria-readonly', 'true')
    })

    // Should show "Viewing version" indicator text
    expect(screen.getByText(/viewing a historical version/i)).toBeInTheDocument()
  })

  it('shows Restore button when viewing historical version', async () => {
    const apiModule = await import('../services/api')
    vi.mocked(apiModule.fetchTemplate).mockImplementation((_id, version) => {
      const v = version === 'latest' ? 3 : (typeof version === 'number' ? version : 1)
      return Promise.resolve({
        template_id: 'tmpl-abc123',
        version: v,
        name: `Template v${v}`,
        description: '',
        user_id: 'user-1',
        is_public: false,
        is_owner: true,
        created_at: '2025-01-01T00:00:00',
        steps: [{ id: 'step1', prompt: 'content' }],
        schema_requirements: [],
      })
    })
    vi.mocked(apiModule.fetchTemplateVersions).mockResolvedValue([
      { version: 3, name: 'Third', description: '', created_at: '2025-01-03T00:00:00' },
      { version: 1, name: 'First', description: '', created_at: '2025-01-01T00:00:00' },
    ])

    render(<TemplateEditor />)

    await waitFor(() => {
      expect(screen.getByText('First')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('First'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Restore This Version/ })).toBeInTheDocument()
    })

    // Save button should NOT be visible when viewing historical
    expect(screen.queryByRole('button', { name: /^Save$|^Update$/ })).not.toBeInTheDocument()
  })

  it('calls updateTemplate when restoring a historical version', async () => {
    const apiModule = await import('../services/api')
    vi.mocked(apiModule.fetchTemplate).mockImplementation((_id, version) => {
      const v = version === 'latest' ? 3 : (typeof version === 'number' ? version : 1)
      return Promise.resolve({
        template_id: 'tmpl-abc123',
        version: v,
        name: `Template v${v}`,
        description: '',
        user_id: 'user-1',
        is_public: false,
        is_owner: true,
        created_at: '2025-01-01T00:00:00',
        steps: [{ id: 'step1', prompt: 'restored content' }],
        schema_requirements: [],
      })
    })
    vi.mocked(apiModule.fetchTemplateVersions).mockResolvedValue([
      { version: 3, name: 'Third', description: '', created_at: '2025-01-03T00:00:00' },
      { version: 1, name: 'First', description: '', created_at: '2025-01-01T00:00:00' },
    ])
    mockUpdateTemplate.mockResolvedValueOnce({
      template_id: 'tmpl-abc123',
      version: 4,
      name: 'Template v1',
    })

    render(<TemplateEditor />)

    await waitFor(() => {
      expect(screen.getByText('First')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('First'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Restore This Version/ })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Restore This Version/ }))

    await waitFor(() => {
      expect(mockUpdateTemplate).toHaveBeenCalledWith('tmpl-abc123', expect.objectContaining({
        steps: [{ id: 'step1', prompt: 'restored content' }],
      }))
    })
  })
})
