import { useState } from 'react'

import { api, ApiError } from '../../lib/api'
import { useAuth } from '../../lib/auth'

/** Run an admin action, keeping its success or error message for display. */
export function useAction() {
  const { auth } = useAuth()
  const token = auth?.token ?? null
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const run = async <T,>(path: string, method: string, body?: unknown, done?: (r: T) => string): Promise<T | undefined> => {
    try {
      const result = await api<T>(path, { method, body, token })
      setMessage(done ? { ok: true, text: done(result) } : null)
      return result
    } catch (e) {
      setMessage({ ok: false, text: (e as ApiError).message })
      return undefined
    }
  }
  return { token, run, message, setMessage }
}

export function Message({ message }: { message: { ok: boolean; text: string } | null }) {
  if (!message) return null
  return message.ok ? <p role="status" className="success">{message.text}</p> : <p role="alert" className="error">{message.text}</p>
}
