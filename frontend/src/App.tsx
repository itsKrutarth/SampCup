import { useEffect, useState } from 'react'

import { fetchApiStatus, type ApiStatus } from './api'

const STATUS_LABEL = {
  checking: 'Checking…',
  online: 'Live',
  offline: 'Offline',
} as const

export default function App() {
  const [status, setStatus] = useState<ApiStatus | 'checking'>('checking')

  useEffect(() => {
    const controller = new AbortController()
    fetchApiStatus(controller.signal).then((result) => {
      if (!controller.signal.aborted) setStatus(result)
    })
    return () => controller.abort()
  }, [])

  return (
    <main className="page">
      <h1>SAMP Cup</h1>
      <p>New England pickleball tournament</p>
      <p className={`badge badge-${status}`} role="status">
        {STATUS_LABEL[status]}
      </p>
    </main>
  )
}
