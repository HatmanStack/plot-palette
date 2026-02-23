import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, createTestQueryClient, mockAuthContextAuthenticated } from '../test/test-utils'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../contexts/AuthContext'
import { ToastProvider } from '../contexts/ToastContext'

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchNotificationPreferences: vi.fn(),
    updateNotificationPreferences: vi.fn(),
  }
})

import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
} from '../services/api'
import Settings from './Settings'

const defaultPrefs = {
  email_enabled: false,
  email_address: null,
  webhook_enabled: false,
  webhook_url: null,
  notify_on_complete: true,
  notify_on_failure: true,
  notify_on_budget_exceeded: true,
}

function renderSettings() {
  const client = createTestQueryClient()
  return render(<Settings />, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={mockAuthContextAuthenticated}>
          <ToastProvider>
            <MemoryRouter initialEntries={['/settings']}>
              {children}
            </MemoryRouter>
          </ToastProvider>
        </AuthContext.Provider>
      </QueryClientProvider>
    ),
    withRouter: false,
  })
}

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads and displays current preferences', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce({
      ...defaultPrefs,
      email_enabled: true,
      email_address: 'user@example.com',
    })

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    const emailCheckbox = screen.getByLabelText('Email notifications') as HTMLInputElement
    expect(emailCheckbox.checked).toBe(true)
  })

  it('email toggle shows/hides email input', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    expect(screen.queryByPlaceholderText('your@email.com')).not.toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Email notifications'))

    expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument()
  })

  it('webhook toggle shows/hides URL input', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    expect(screen.queryByPlaceholderText('https://example.com/webhook')).not.toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Webhook notifications'))

    expect(screen.getByPlaceholderText('https://example.com/webhook')).toBeInTheDocument()
  })

  it('rejects HTTP webhook URL', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce({
      ...defaultPrefs,
      webhook_enabled: true,
      webhook_url: null,
    })

    renderSettings()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('https://example.com/webhook')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('https://example.com/webhook'), {
      target: { value: 'http://example.com/webhook' },
    })

    fireEvent.click(screen.getByText('Save Preferences'))

    expect(screen.getByText('Webhook URL must start with https://')).toBeInTheDocument()
  })

  it('save button disabled when no changes', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    const saveButton = screen.getByText('Save Preferences') as HTMLButtonElement
    expect(saveButton.disabled).toBe(true)
  })

  it('save calls API with updated preferences', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)
    vi.mocked(updateNotificationPreferences).mockResolvedValueOnce({
      ...defaultPrefs,
      email_enabled: true,
    })

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Email notifications'))
    fireEvent.click(screen.getByText('Save Preferences'))

    await waitFor(() => {
      expect(updateNotificationPreferences).toHaveBeenCalled()
      const callArg = vi.mocked(updateNotificationPreferences).mock.calls[0][0]
      expect(callArg).toEqual(expect.objectContaining({ email_enabled: true }))
    })
  })

  it('shows success toast on save', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)
    vi.mocked(updateNotificationPreferences).mockResolvedValueOnce({
      ...defaultPrefs,
      notify_on_failure: false,
    })

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Job failure'))
    fireEvent.click(screen.getByText('Save Preferences'))

    await waitFor(() => {
      expect(screen.getByText('Preferences saved')).toBeInTheDocument()
    })
  })

  it('shows error toast on save failure', async () => {
    vi.mocked(fetchNotificationPreferences).mockResolvedValueOnce(defaultPrefs)
    vi.mocked(updateNotificationPreferences).mockRejectedValueOnce(new Error('Network error'))

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Email notifications'))
    fireEvent.click(screen.getByText('Save Preferences'))

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })
})
