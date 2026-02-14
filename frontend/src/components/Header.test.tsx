import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '../test/test-utils'
import type { AuthContextType } from '../contexts/AuthContext'
import Header from './Header'

describe('Header', () => {
  const mockLogout = vi.fn()

  const authContext: AuthContextType = {
    isAuthenticated: true,
    idToken: 'mock-token',
    login: vi.fn(),
    signup: vi.fn(),
    logout: mockLogout,
    loading: false,
  }

  it('renders welcome message', () => {
    render(<Header />, { authContext })
    expect(screen.getByText('Welcome to Plot Palette')).toBeInTheDocument()
  })

  it('renders logout button', () => {
    render(<Header />, { authContext })
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument()
  })

  it('calls logout when button is clicked', () => {
    render(<Header />, { authContext })
    fireEvent.click(screen.getByRole('button', { name: 'Logout' }))
    expect(mockLogout).toHaveBeenCalledOnce()
  })
})
