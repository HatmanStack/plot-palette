import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import QualityScoreBar from './QualityScoreBar'

describe('QualityScoreBar', () => {
  it('renders bar with correct fill percentage', () => {
    const { container } = render(
      <QualityScoreBar score={0.75} label="Coherence" />
    )

    const progressBar = container.querySelector('[role="progressbar"]')
    expect(progressBar).toBeTruthy()
    expect(progressBar?.getAttribute('style')).toContain('width: 75%')
  })

  it('shows green color for score >= 0.8', () => {
    const { container } = render(
      <QualityScoreBar score={0.85} label="Test" />
    )

    const bar = container.querySelector('[role="progressbar"]')
    expect(bar?.className).toContain('bg-green-500')
  })

  it('shows yellow color for score >= 0.6', () => {
    const { container } = render(
      <QualityScoreBar score={0.65} label="Test" />
    )

    const bar = container.querySelector('[role="progressbar"]')
    expect(bar?.className).toContain('bg-yellow-500')
  })

  it('shows red color for score < 0.6', () => {
    const { container } = render(
      <QualityScoreBar score={0.4} label="Test" />
    )

    const bar = container.querySelector('[role="progressbar"]')
    expect(bar?.className).toContain('bg-red-500')
  })

  it('shows numeric score label', () => {
    render(<QualityScoreBar score={0.85} label="Coherence" />)

    expect(screen.getByTestId('score-value')).toHaveTextContent('0.85')
    expect(screen.getByText('Coherence')).toBeTruthy()
  })
})
