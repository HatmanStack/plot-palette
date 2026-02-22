import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  describe('Renders correct label for each status', () => {
    it('displays "Queued" for QUEUED status', () => {
      render(<StatusBadge status="QUEUED" />)
      expect(screen.getByText('Queued')).toBeInTheDocument()
    })

    it('displays "Running" for RUNNING status', () => {
      render(<StatusBadge status="RUNNING" />)
      expect(screen.getByText('Running')).toBeInTheDocument()
    })

    it('displays "Completed" for COMPLETED status', () => {
      render(<StatusBadge status="COMPLETED" />)
      expect(screen.getByText('Completed')).toBeInTheDocument()
    })

    it('displays "Failed" for FAILED status', () => {
      render(<StatusBadge status="FAILED" />)
      expect(screen.getByText('Failed')).toBeInTheDocument()
    })

    it('displays "Cancelled" for CANCELLED status', () => {
      render(<StatusBadge status="CANCELLED" />)
      expect(screen.getByText('Cancelled')).toBeInTheDocument()
    })

    it('displays "Budget Exceeded" for BUDGET_EXCEEDED status', () => {
      render(<StatusBadge status="BUDGET_EXCEEDED" />)
      expect(screen.getByText('Budget Exceeded')).toBeInTheDocument()
    })
  })

  describe('Behavioral styling', () => {
    it('applies animate-pulse to RUNNING status only', () => {
      const { rerender } = render(<StatusBadge status="RUNNING" />)
      expect(screen.getByText('Running').className).toContain('animate-pulse')

      rerender(<StatusBadge status="COMPLETED" />)
      expect(screen.getByText('Completed').className).not.toContain('animate-pulse')
    })

    it('renders all valid statuses without error', () => {
      const statuses = ['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXCEEDED'] as const
      for (const status of statuses) {
        const { unmount } = render(<StatusBadge status={status} />)
        expect(screen.getByText(/./)).toBeInTheDocument()
        unmount()
      }
    })
  })
})
