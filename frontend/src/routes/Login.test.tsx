import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '../test/test-utils'
import type { AuthContextType } from '../contexts/AuthContext'
import Login from './Login'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function getEmailInput() {
  return screen.getByRole('textbox')
}

function getPasswordInput() {
  return document.querySelector('input[type="password"]') as HTMLInputElement
}

describe('Login', () => {
  const mockLogin = vi.fn()

  const authContext: AuthContextType = {
    isAuthenticated: false,
    idToken: null,
    login: mockLogin,
    signup: vi.fn(),
    logout: vi.fn(),
    loading: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form', () => {
    render(<Login />, { authContext })
    expect(screen.getByText('Plot Palette')).toBeInTheDocument()
    expect(screen.getByText('Sign in to your account')).toBeInTheDocument()
    expect(getEmailInput()).toBeInTheDocument()
    expect(getPasswordInput()).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('has link to signup page', () => {
    render(<Login />, { authContext })
    expect(screen.getByText('Sign up')).toHaveAttribute('href', '/signup')
  })

  it('submits form and navigates on success', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    render(<Login />, { authContext })

    fireEvent.change(getEmailInput(), { target: { value: 'test@example.com' } })
    fireEvent.change(getPasswordInput(), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByRole('button', { name: 'Signing in...' })).toBeDisabled()

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123')
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('displays error message on login failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Incorrect username or password.'))
    render(<Login />, { authContext })

    fireEvent.change(getEmailInput(), { target: { value: 'test@example.com' } })
    fireEvent.change(getPasswordInput(), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByText('Incorrect username or password.')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('displays generic error for non-Error throws', async () => {
    mockLogin.mockRejectedValueOnce('string error')
    render(<Login />, { authContext })

    fireEvent.change(getEmailInput(), { target: { value: 'test@example.com' } })
    fireEvent.change(getPasswordInput(), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByText('Failed to login')).toBeInTheDocument()
    })
  })

  it('re-enables button after failed login', async () => {
    mockLogin.mockRejectedValueOnce(new Error('fail'))
    render(<Login />, { authContext })

    fireEvent.change(getEmailInput(), { target: { value: 'a@b.com' } })
    fireEvent.change(getPasswordInput(), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign in' })).not.toBeDisabled()
    })
  })
})
