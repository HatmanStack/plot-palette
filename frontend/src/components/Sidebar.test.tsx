import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import Sidebar from './Sidebar'

describe('Sidebar', () => {
  it('renders brand name', () => {
    render(<Sidebar />)
    expect(screen.getByText('Plot Palette')).toBeInTheDocument()
    expect(screen.getByText('Synthetic Data Generator')).toBeInTheDocument()
  })

  it('renders all navigation links', () => {
    render(<Sidebar />)
    expect(screen.getByText('Dashboard')).toHaveAttribute('href', '/dashboard')
    expect(screen.getByText('Jobs')).toHaveAttribute('href', '/jobs')
    expect(screen.getByText('Templates')).toHaveAttribute('href', '/templates')
    expect(screen.getByText('Settings')).toHaveAttribute('href', '/settings')
  })

  it('highlights the active route', () => {
    render(<Sidebar />, { initialEntries: ['/jobs'] })
    const jobsLink = screen.getByText('Jobs').closest('a')
    expect(jobsLink?.className).toContain('bg-blue-600')

    const dashboardLink = screen.getByText('Dashboard').closest('a')
    expect(dashboardLink?.className).not.toContain('bg-blue-600')
  })
})
