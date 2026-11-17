import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError } from './api'

const listeners = new Set<() => void>()
let source: EventSource | null = null

function connect(): void {
  if (source || typeof EventSource === 'undefined') return
  source = new EventSource('/api/public/stream')
  const notify = () => listeners.forEach((listener) => listener())
  source.addEventListener('update', notify)
  source.addEventListener('hello', notify) // reconnected: refetch everything
}

/** Call `onChange` (at most once a second) whenever the server says data changed. */
export function useLiveUpdates(onChange: () => void, waitMs = 1000): void {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    const listener = () => {
      if (timer.current) return
      timer.current = setTimeout(() => {
        timer.current = null
        onChange()
      }, waitMs)
    }
    listeners.add(listener)
    connect()
    return () => {
      listeners.delete(listener)
      if (timer.current) clearTimeout(timer.current)
      timer.current = null
      if (listeners.size === 0 && source) {
        source.close()
        source = null
      }
    }
  }, [onChange, waitMs])
}

type State<T> = { key?: string; data?: T; error?: ApiError }

/** GET `path` (null = skip), refetched on live updates and on `reload()`. */
export function useApi<T>(path: string | null, token?: string | null) {
  const [state, setState] = useState<State<T>>({})
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((v) => v + 1), [])
  useLiveUpdates(reload)
  const key = path === null ? undefined : `${token ?? ''} ${path}`
  useEffect(() => {
    if (path === null) return
    let cancelled = false
    api<T>(path, { token }).then(
      (data) => !cancelled && setState({ key, data }),
      (error: ApiError) => !cancelled && setState((s) => ({ ...s, key, error })),
    )
    return () => {
      cancelled = true
    }
  }, [path, token, key, version])
  const current = state.key === key
  return {
    data: state.data,
    error: current ? state.error : undefined,
    loading: path !== null && !current,
    reload,
  }
}
