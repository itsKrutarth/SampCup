import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import Intro from './Intro'

function motion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: reduce && query.includes('reduce') }))
}

describe('opening animation', () => {
  afterEach(() => sessionStorage.clear())

  it('plays once per visit and ends on its own', () => {
    vi.useFakeTimers()
    motion(false)
    const { unmount } = render(<Intro />)
    expect(screen.getByTestId('intro')).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(2700)
    })
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
    unmount()
    render(<Intro />)
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument() // already seen this visit
    vi.useRealTimers()
  })

  it('can be skipped with a tap or Escape, and ends when its animation ends', () => {
    motion(false)
    const first = render(<Intro />)
    fireEvent.click(screen.getByTestId('intro'))
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
    first.unmount()
    sessionStorage.clear()
    const second = render(<Intro />)
    fireEvent.keyDown(window, { key: 'Enter' })
    expect(screen.getByTestId('intro')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
    second.unmount()
    sessionStorage.clear()
    render(<Intro />)
    const overlay = screen.getByTestId('intro')
    fireEvent.animationEnd(overlay.querySelector('.intro-ball')!)
    expect(screen.getByTestId('intro')).toBeInTheDocument() // a part finishing is not the end
    fireEvent.animationEnd(overlay)
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
  })

  it('stays off for people who ask for less motion, or without storage', () => {
    motion(true)
    render(<Intro />)
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
    motion(false)
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<Intro />)
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument()
  })

  it('still plays when the visit cannot be remembered', () => {
    motion(false)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<Intro />)
    expect(screen.getByTestId('intro')).toBeInTheDocument()
  })
})
