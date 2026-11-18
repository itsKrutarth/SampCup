import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { fail, mockApi } from '../test/utils'
import { api, ApiError, download } from './api'
import { clock, dateLong, monthDay, time, venueTimeToIso, weekday } from './format'
import { useApi, useLiveUpdates } from './live'
import { load, save } from './storage'

describe('api', () => {
  it('sends JSON with the token and reads JSON back', async () => {
    const { calls } = mockApi({ 'POST /things': { ok: true } })
    await expect(api('/things', { method: 'POST', body: { a: 1 }, token: 'tok' })).resolves.toEqual({ ok: true })
    expect(calls[0].body).toEqual({ a: 1 })
    expect(calls[0].headers).toEqual({ Authorization: 'Bearer tok', 'Content-Type': 'application/json' })
  })

  it('returns nothing for 204 and sends forms as they are', async () => {
    const { calls } = mockApi({ 'DELETE /things/1': null, 'POST /upload': { added: 1 } })
    await expect(api('/things/1', { method: 'DELETE' })).resolves.toBeUndefined()
    const form = new FormData()
    await api('/upload', { method: 'POST', form })
    expect(calls[1].body).toBe(form)
    expect(calls[1].headers).toEqual({})
  })

  it('turns server errors into readable messages', async () => {
    mockApi({
      'GET /a': fail(409, 'Already final'),
      'GET /b': new Response(JSON.stringify({ detail: [{ msg: 'too long' }, { msg: 'bad' }] }), { status: 422 }),
      'GET /c': new Response('oops', { status: 500 }),
    })
    await expect(api('/a')).rejects.toMatchObject({ status: 409, message: 'Already final' })
    await expect(api('/b')).rejects.toMatchObject({ message: 'too long; bad' })
    await expect(api('/c')).rejects.toMatchObject({ message: 'Request failed (500)' })
  })

  it('reports a network failure as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')))
    const error = await api('/x').catch((e: ApiError) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0 })
  })

  it('downloads a file that needs a login', async () => {
    mockApi({ 'GET /admin/export/results.csv': new Response('a,b\n') })
    const create = vi.fn(() => 'blob:x')
    const revoke = vi.fn()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await download('/admin/export/results.csv', 'tok', 'r.csv')
    expect(click).toHaveBeenCalled()
    expect(revoke).toHaveBeenCalledWith('blob:x')
  })
})

describe('storage', () => {
  it('round-trips values and survives blocked storage', () => {
    save('k', { a: 1 })
    expect(load('k', null)).toEqual({ a: 1 })
    save('k', null)
    expect(load('k', 'fallback')).toBe('fallback')
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(load('k', 7)).toBe(7)
    expect(() => save('k', 1)).not.toThrow()
  })
})

describe('format', () => {
  it('shows venue times and clocks', () => {
    expect(time('2026-12-12T15:00:00Z')).toBe('10:00 AM')
    expect(time(null)).toBe('')
    expect(clock(725.4)).toBe('12:05')
    expect(clock(-3)).toBe('0:00')
    expect(dateLong('2026-12-12')).toBe('Saturday, December 12, 2026')
    expect(dateLong(null)).toBe('Date to be announced')
    expect(monthDay('2026-12-06')).toBe('December 6')
    expect(weekday('2026-12-06')).toBe('Sunday')
  })

  it('converts venue time to UTC in winter and summer', () => {
    expect(venueTimeToIso('2026-12-12', '14:30')).toBe('2026-12-12T19:30:00.000Z')
    expect(venueTimeToIso('2026-07-04', '14:30')).toBe('2026-07-04T18:30:00.000Z')
  })
})

describe('live data', () => {
  it('loads, reloads, and polls while the page is visible', async () => {
    let n = 0
    mockApi({ 'GET /count': () => ({ n: ++n }) })
    const { result, unmount } = renderHook(() => useApi<{ n: number }>('/count', null, 30))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.data?.n).toBeGreaterThanOrEqual(1))
    const seen = result.current.data!.n
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.data!.n).toBeGreaterThan(seen))
    unmount()
  })

  it('keeps the error and skips null paths', async () => {
    mockApi({ 'GET /broken': fail(500, 'boom') })
    const { result } = renderHook(() => useApi('/broken'))
    await waitFor(() => expect(result.current.error?.message).toBe('boom'))
    const skipped = renderHook(() => useApi(null))
    expect(skipped.result.current.loading).toBe(false)
  })

  it('pauses while hidden and refreshes on return or reconnect', async () => {
    const onChange = vi.fn()
    let state: DocumentVisibilityState = 'hidden'
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => state)
    const { unmount } = renderHook(() => useLiveUpdates(onChange, 10))
    await new Promise((r) => setTimeout(r, 40))
    expect(onChange).not.toHaveBeenCalled()
    state = 'visible'
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event('online'))
    })
    expect(onChange).toHaveBeenCalledTimes(2)
    await waitFor(() => expect(onChange.mock.calls.length).toBeGreaterThan(2))
    unmount()
    const calls = onChange.mock.calls.length
    await new Promise((r) => setTimeout(r, 40))
    expect(onChange).toHaveBeenCalledTimes(calls)
  })
})
