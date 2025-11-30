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

  describe('Applies correct styling classes', () => {
    it('applies gray styling for QUEUED', () => {
      render(<StatusBadge status="QUEUED" />)
      const badge = screen.getByText('Queued')
      expect(badge).toHaveClass('bg-gray-100', 'text-gray-700', 'border-gray-300')
    })

    it('applies blue styling with pulse animation for RUNNING', () => {
      render(<StatusBadge status="RUNNING" />)
      const badge = screen.getByText('Running')
      expect(badge).toHaveClass('bg-blue-100', 'text-blue-700', 'border-blue-300', 'animate-pulse')
    })

    it('applies green styling for COMPLETED', () => {
      render(<StatusBadge status="COMPLETED" />)
      const badge = screen.getByText('Completed')
      expect(badge).toHaveClass('bg-green-100', 'text-green-700', 'border-green-300')
    })

    it('applies red styling for FAILED', () => {
      render(<StatusBadge status="FAILED" />)
      const badge = screen.getByText('Failed')
      expect(badge).toHaveClass('bg-red-100', 'text-red-700', 'border-red-300')
    })

    it('applies yellow styling for CANCELLED', () => {
      render(<StatusBadge status="CANCELLED" />)
      const badge = screen.getByText('Cancelled')
      expect(badge).toHaveClass('bg-yellow-100', 'text-yellow-700', 'border-yellow-300')
    })

    it('applies orange styling for BUDGET_EXCEEDED', () => {
      render(<StatusBadge status="BUDGET_EXCEEDED" />)
      const badge = screen.getByText('Budget Exceeded')
      expect(badge).toHaveClass('bg-orange-100', 'text-orange-700', 'border-orange-300')
    })
  })

  describe('Common badge styling', () => {
    it('has rounded-full class for pill shape', () => {
      render(<StatusBadge status="COMPLETED" />)
      const badge = screen.getByText('Completed')
      expect(badge).toHaveClass('rounded-full')
    })

    it('has small text and font-medium', () => {
      render(<StatusBadge status="COMPLETED" />)
      const badge = screen.getByText('Completed')
      expect(badge).toHaveClass('text-xs', 'font-medium')
    })

    it('has border class', () => {
      render(<StatusBadge status="COMPLETED" />)
      const badge = screen.getByText('Completed')
      expect(badge).toHaveClass('border')
    })

    it('has padding classes', () => {
      render(<StatusBadge status="COMPLETED" />)
      const badge = screen.getByText('Completed')
      expect(badge).toHaveClass('px-2', 'py-1')
    })
  })
})
