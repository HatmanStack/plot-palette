import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '../test/test-utils'
import type { AuthContextType } from '../contexts/AuthContext'
import Signup from './Signup'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function getEmailInput() {
  return screen.getByRole('textbox')
}

function getPasswordInputs() {
  return document.querySelectorAll('input[type="password"]') as NodeListOf<HTMLInputElement>
}

function fillForm(email: string, password: string, confirm: string) {
  fireEvent.change(getEmailInput(), { target: { value: email } })
  const [pwInput, confirmInput] = getPasswordInputs()
  fireEvent.change(pwInput, { target: { value: password } })
  fireEvent.change(confirmInput, { target: { value: confirm } })
}

describe('Signup', () => {
  const mockSignup = vi.fn()

  const authContext: AuthContextType = {
    isAuthenticated: false,
    idToken: null,
    login: vi.fn(),
    signup: mockSignup,
    logout: vi.fn(),
    loading: false,
  }

  const validPassword = 'StrongPass1!xy'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders signup form', () => {
    render(<Signup />, { authContext })
    expect(screen.getByText('Plot Palette')).toBeInTheDocument()
    expect(screen.getByText('Create your account')).toBeInTheDocument()
    expect(getEmailInput()).toBeInTheDocument()
    expect(getPasswordInputs()).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Sign up' })).toBeInTheDocument()
  })

  it('has link to login page', () => {
    render(<Signup />, { authContext })
    expect(screen.getByText('Sign in')).toHaveAttribute('href', '/login')
  })

  it('shows error when passwords do not match', () => {
    render(<Signup />, { authContext })
    fillForm('a@b.com', validPassword, 'different')
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
    expect(mockSignup).not.toHaveBeenCalled()
  })

  it('shows error when password is too short', () => {
    render(<Signup />, { authContext })
    fillForm('a@b.com', 'Short1!', 'Short1!')
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    expect(screen.getByText('Password must be at least 12 characters long')).toBeInTheDocument()
    expect(mockSignup).not.toHaveBeenCalled()
  })

  it('shows error when password lacks complexity', () => {
    render(<Signup />, { authContext })
    fillForm('a@b.com', 'alllowercase1', 'alllowercase1')
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    expect(screen.getByText('Password must include uppercase, lowercase, number, and special character')).toBeInTheDocument()
    expect(mockSignup).not.toHaveBeenCalled()
  })

  it('shows success message after successful signup', async () => {
    mockSignup.mockResolvedValueOnce(undefined)
    render(<Signup />, { authContext })

    fillForm('new@example.com', validPassword, validPassword)
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    await waitFor(() => {
      expect(screen.getByText('Success!')).toBeInTheDocument()
      expect(screen.getByText(/check your email/)).toBeInTheDocument()
    })
  })

  it('redirects to login after successful signup', async () => {
    vi.useFakeTimers()
    mockSignup.mockResolvedValueOnce(undefined)
    render(<Signup />, { authContext })

    fillForm('new@example.com', validPassword, validPassword)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))
      // Flush microtasks for the async signup
      await Promise.resolve()
    })

    // Now advance the redirect timeout
    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(mockNavigate).toHaveBeenCalledWith('/login')
    vi.useRealTimers()
  })

  it('displays error on signup failure', async () => {
    mockSignup.mockRejectedValueOnce(new Error('User already exists'))
    render(<Signup />, { authContext })

    fillForm('a@b.com', validPassword, validPassword)
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    await waitFor(() => {
      expect(screen.getByText('User already exists')).toBeInTheDocument()
    })
  })

  it('displays generic error for non-Error throws', async () => {
    mockSignup.mockRejectedValueOnce('string error')
    render(<Signup />, { authContext })

    fillForm('a@b.com', validPassword, validPassword)
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    await waitFor(() => {
      expect(screen.getByText('Failed to sign up')).toBeInTheDocument()
    })
  })

  it('disables button during submission', async () => {
    let resolveSignup: () => void
    mockSignup.mockImplementation(() => new Promise<void>((r) => { resolveSignup = r }))
    render(<Signup />, { authContext })

    fillForm('a@b.com', validPassword, validPassword)
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Creating account...' })).toBeDisabled()
    })

    // Clean up — resolve the pending promise
    await act(async () => { resolveSignup!() })
  })
})
