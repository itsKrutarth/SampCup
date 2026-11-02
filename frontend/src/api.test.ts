import { describe, expect, it, vi } from 'vitest'

import { fetchApiStatus } from './api'

describe('fetchApiStatus', () => {
  it('is online when the API answers OK', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
    await expect(fetchApiStatus()).resolves.toBe('online')
    expect(fetch).toHaveBeenCalledWith('/api/health', { signal: undefined })
  })

  it('is offline when the API returns an error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await expect(fetchApiStatus()).resolves.toBe('offline')
  })

  it('is offline when the network fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
    await expect(fetchApiStatus()).resolves.toBe('offline')
  })
})
