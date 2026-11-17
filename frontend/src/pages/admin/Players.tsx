import { useState, type FormEvent } from 'react'

import Status from '../../components/Status'
import { api, ApiError } from '../../lib/api'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

export type AdminPlayer = {
  id: number
  mis_id: string
  first_name: string
  last_name: string
  center: string
  zone: string
  tshirt_size: string
  active: boolean
  team: { id: number; name: string } | null
}

type Report = {
  added: number
  updated: number
  unchanged: number
  deactivated: number
  possible_duplicates: string[]
  skipped: { row: number; reason: string }[]
  teams_with_removed_players: string[]
}

export default function Players() {
  const { token, message, setMessage } = useAction()
  const { data, loading, error, reload } = useApi<AdminPlayer[]>('/admin/players', token)
  const [report, setReport] = useState<Report | null>(null)
  const [filter, setFilter] = useState('')
  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const file = (event.currentTarget.elements.namedItem('file') as HTMLInputElement).files?.[0]
    if (!file) {
      setMessage({ ok: false, text: 'Choose the registration export first' })
      return
    }
    const form = new FormData()
    form.append('file', file)
    try {
      setReport(await api<Report>('/admin/players/import', { method: 'POST', form, token }))
      setMessage(null)
      reload()
    } catch (e) {
      setMessage({ ok: false, text: (e as ApiError).message })
    }
  }
  const shown = (data ?? []).filter((p) =>
    `${p.first_name} ${p.last_name} ${p.center} ${p.mis_id}`.toLowerCase().includes(filter.toLowerCase()),
  )
  return (
    <>
      <form onSubmit={upload} className="stack">
        <h2>Import registrations</h2>
        <p className="hint">Upload the registration export (.xlsx or .csv). Players are matched by MISID; nobody is deleted.</p>
        <input name="file" type="file" accept=".xlsx,.csv" aria-label="Registration file" />
        <button type="submit">Import</button>
      </form>
      <Message message={message} />
      {report && (
        <div role="status" className="card">
          <p>
            Added {report.added}, updated {report.updated}, unchanged {report.unchanged}, deactivated {report.deactivated}.
          </p>
          {report.skipped.length > 0 && <p>Skipped rows: {report.skipped.map((s) => `${s.row} (${s.reason})`).join(', ')}</p>}
          {report.possible_duplicates.length > 0 && <p>Check for duplicates: {report.possible_duplicates.join(', ')}</p>}
          {report.teams_with_removed_players.length > 0 && <p>Teams with removed players: {report.teams_with_removed_players.join(', ')}</p>}
        </div>
      )}
      <h2>Players ({data?.length ?? 0})</h2>
      <input placeholder="Search name, center or MISID" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Search players" />
      <Status loading={loading} error={error} />
      <table>
        <thead>
          <tr><th>Name</th><th>Center</th><th>MISID</th><th>Shirt</th><th>Team</th></tr>
        </thead>
        <tbody>
          {shown.map((p) => (
            <tr key={p.id} className={p.active ? '' : 'inactive'}>
              <td>{p.first_name} {p.last_name}{p.active ? '' : ' (removed)'}</td>
              <td>{p.center}</td>
              <td>{p.mis_id}</td>
              <td>{p.tshirt_size}</td>
              <td>{p.team?.name ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
