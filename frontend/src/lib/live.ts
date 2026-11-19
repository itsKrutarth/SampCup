import { useCallback, useEffect, useState } from 'react'

import { api, ApiError } from './api'

/**
 * Call `onChange` every few seconds while the page is visible, and at once when the
 * page comes back into view or the connection returns. Public answers are cached by
 * CloudFront for a few seconds, so many open phones cost almost nothing.
 */
export function useLiveUpdates(onChange: () => void, everyMs = 4000): void {
  useEffect(() => {
    const visible = () => document.visibilityState !== 'hidden'
    const id = setInterval(() => visible() && onChange(), everyMs)
    const onShow = () => visible() && onChange()
    document.addEventListener('visibilitychange', onShow)
    window.addEventListener('online', onChange)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onShow)
      window.removeEventListener('online', onChange)
    }
  }, [onChange, everyMs])
}

type State<T> = { key?: string; data?: T; at?: number; error?: ApiError }

/** GET `path` (null = skip), refetched on live updates and on `reload()`. */
export function useApi<T>(path: string | null, token?: string | null, everyMs = 4000) {
  const [state, setState] = useState<State<T>>({})
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((v) => v + 1), [])
  useLiveUpdates(reload, everyMs)
  const key = path === null ? undefined : `${token ?? ''} ${path}`
  useEffect(() => {
    if (path === null) return
    let cancelled = false
    api<T>(path, { token }).then(
      (data) => !cancelled && setState({ key, data, at: Date.now() }),
      (error: ApiError) => !cancelled && setState((s) => ({ ...s, key, error })),
    )
    return () => {
      cancelled = true
    }
  }, [path, token, key, version])
  const current = state.key === key
  return {
    data: state.data,
    /** When `data` arrived (ms), e.g. to line a countdown up with a server time in it. */
    receivedAt: state.at,
    error: current ? state.error : undefined,
    loading: path !== null && !current,
    reload,
  }
}
