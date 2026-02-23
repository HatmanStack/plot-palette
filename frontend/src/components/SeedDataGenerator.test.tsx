import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../contexts/ToastContext'
import SeedDataGenerator from './SeedDataGenerator'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  generateSeedData: vi.fn(),
}))

const mockGenerateSeedData = vi.mocked(api.generateSeedData)

describe('SeedDataGenerator', () => {
  const mockOnGenerated = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderGenerator = (templateId = 'tmpl-123') => {
    return render(
      <MemoryRouter>
        <ToastProvider>
          <SeedDataGenerator templateId={templateId} onGenerated={mockOnGenerated} />
        </ToastProvider>
      </MemoryRouter>
    )
  }

  it('renders count input and generate button', () => {
    renderGenerator()
    expect(screen.getByDisplayValue('10')).toBeInTheDocument()
    expect(screen.getByText(/Generate 10 Records/)).toBeInTheDocument()
  })

  it('calls API with correct parameters on generate', async () => {
    mockGenerateSeedData.mockResolvedValueOnce({
      s3_key: 'seed-data/user-123/generated-test.jsonl',
      records_generated: 10,
      records_invalid: 0,
      total_cost: 0.01,
    })

    renderGenerator()
    const user = userEvent.setup()

    await user.click(screen.getByText(/Generate 10 Records/))

    expect(mockGenerateSeedData).toHaveBeenCalledWith({
      template_id: 'tmpl-123',
      count: 10,
      model_tier: 'tier-1',
      example_data: undefined,
      instructions: undefined,
    })
  })

  it('shows loading state during generation', async () => {
    let resolvePromise: (value: api.SeedDataGenerationResult) => void
    mockGenerateSeedData.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve
      })
    )

    renderGenerator()
    const user = userEvent.setup()

    await user.click(screen.getByText(/Generate 10 Records/))
    expect(screen.getByText('Generating...')).toBeInTheDocument()

    // Resolve the promise
    resolvePromise!({
      s3_key: 'seed-data/test.jsonl',
      records_generated: 10,
      records_invalid: 0,
      total_cost: 0.01,
    })

    await waitFor(() => {
      expect(screen.queryByText('Generating...')).not.toBeInTheDocument()
    })
  })

  it('shows success with record count on completion', async () => {
    mockGenerateSeedData.mockResolvedValueOnce({
      s3_key: 'seed-data/user-123/generated-test.jsonl',
      records_generated: 8,
      records_invalid: 2,
      total_cost: 0.05,
    })

    renderGenerator()
    const user = userEvent.setup()

    await user.click(screen.getByText(/Generate 10 Records/))

    await waitFor(() => {
      expect(screen.getByText(/Generated 8 records/)).toBeInTheDocument()
      expect(screen.getByText(/2 invalid filtered/)).toBeInTheDocument()
    })
  })

  it('shows error toast on failure', async () => {
    mockGenerateSeedData.mockRejectedValueOnce(new Error('Bedrock call failed'))

    renderGenerator()
    const user = userEvent.setup()

    await user.click(screen.getByText(/Generate 10 Records/))

    await waitFor(() => {
      expect(screen.queryByText('Generating...')).not.toBeInTheDocument()
    })

    // Button should be re-enabled after failure
    expect(screen.getByText(/Generate 10 Records/)).not.toBeDisabled()
  })

  it('calls onGenerated callback with s3_key', async () => {
    mockGenerateSeedData.mockResolvedValueOnce({
      s3_key: 'seed-data/user-123/generated-test.jsonl',
      records_generated: 10,
      records_invalid: 0,
      total_cost: 0.01,
    })

    renderGenerator()
    const user = userEvent.setup()

    await user.click(screen.getByText(/Generate 10 Records/))

    await waitFor(() => {
      expect(mockOnGenerated).toHaveBeenCalledWith(
        'seed-data/user-123/generated-test.jsonl',
        10
      )
    })
  })
})
