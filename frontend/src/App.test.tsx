import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'

describe('App', () => {
  it('shows the tournament name and starts by checking the API', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    render(<App />)
    expect(screen.getByRole('heading', { name: 'SAMP Cup' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Checking…')
  })

  it('shows Live when the API is up', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
    render(<App />)
    expect(await screen.findByText('Live')).toHaveClass('badge-online')
  })

  it('shows Offline when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
    render(<App />)
    expect(await screen.findByText('Offline')).toHaveClass('badge-offline')
  })

  it('ignores a late answer after leaving the page', async () => {
    let answer: (response: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => (answer = resolve))
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pending))
    const { unmount } = render(<App />)
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal
    unmount()
    answer(new Response('{}'))
    await pending
    expect(signal?.aborted).toBe(true)
  })
})
