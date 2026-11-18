import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'

import { AppRoutes } from '../App'
import { AuthProvider, type Auth } from '../lib/auth'

type Context = { body: unknown; url: URL; init: RequestInit }
type Handler = unknown | ((ctx: Context) => unknown)
export type Call = { method: string; path: string; body: unknown; headers: Record<string, string> }

export function fail(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), { status })
}

/** Stub fetch with "METHOD /path" (with or without the query) handlers. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init.method ?? 'GET'
    const path = url.pathname.replace(/^\/api/, '')
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    calls.push({ method, path: path + url.search, body, headers: (init.headers ?? {}) as Record<string, string> })
    const full = `${method} ${path}${url.search}`
    const handler = full in routes ? routes[full] : routes[`${method} ${path}`]
    if (handler === undefined) return fail(404, `No mock for ${full}`)
    const result = typeof handler === 'function' ? await (handler as (c: Context) => unknown)({ body, url, init }) : handler
    if (result instanceof Response) return result.clone()
    if (result === null) return new Response(null, { status: 204 })
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock, sent: (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path) }
}

export const ADMIN: Auth = { token: 't-admin', kind: 'staff', name: 'Admin', role: 'admin', court: null }
export const JUDGE: Auth = { token: 't-judge', kind: 'staff', name: 'Judge One', role: 'judge', court: 1 }
export const PLAYER: Auth = { token: 't-player', kind: 'player', name: 'Aarav' }

export function renderAt(path: string, auth?: Auth) {
  if (auth) localStorage.setItem('sampcup-auth', JSON.stringify(auth))
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  )
}
