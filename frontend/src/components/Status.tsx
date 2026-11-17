import type { ApiError } from '../lib/api'

export default function Status({ loading, error }: { loading?: boolean; error?: ApiError }) {
  if (error) return <p role="alert" className="error">{error.message}</p>
  if (loading) return <p aria-busy="true">Loading…</p>
  return null
}
