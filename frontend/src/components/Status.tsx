import { AlertTriangle } from 'lucide-react'

import type { ApiError } from '../lib/api'

export default function Status({ loading, error }: { loading?: boolean; error?: ApiError }) {
  if (error) {
    return (
      <p role="alert" className="error">
        <AlertTriangle size={18} />
        {error.message}
      </p>
    )
  }
  if (loading) return <p aria-busy="true" className="muted">Loading…</p>
  return null
}
