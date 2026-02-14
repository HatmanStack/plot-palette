import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'
import Jobs from './Jobs'
import Templates from './Templates'
import Settings from './Settings'

describe('Jobs stub page', () => {
  it('renders heading', () => {
    render(<Jobs />)
    expect(screen.getByText('Jobs')).toBeInTheDocument()
  })
})

describe('Templates stub page', () => {
  it('renders heading', () => {
    render(<Templates />)
    expect(screen.getByText('Templates')).toBeInTheDocument()
  })
})

describe('Settings stub page', () => {
  it('renders heading', () => {
    render(<Settings />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })
})
