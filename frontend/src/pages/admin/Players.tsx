import { useState, type FormEvent } from 'react'

import Status from '../../components/Status'
import { api, ApiError } from '../../lib/api'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

// rows imported without a center come in blank (an admin sets it below, or teams them up)
export const NO_CENTER = 'No center'

export type AdminPlayer = {
  id: number
  mis_id: string
  baps_id?: string
  email?: string
  has_email?: boolean
  card_name?: string
  registered_at?: string
  first_name: string
  last_name: string
  center: string
  zone: string
  tshirt_size: string
  active: boolean
  team: { id: number; name: string } | null
  username: string | null
  must_change_password: boolean
}

type Report = {
  preview?: boolean
  added: number
  updated: number
  unchanged: number
  deactivated: number
  added_names?: string[]
  updated_names?: string[]
  center_changes?: string[]
  deactivated_names?: string[]
  no_center?: string[]
  no_email?: string[]
  possible_duplicates: string[]
  skipped: { row: number; reason: string }[]
  teams_with_removed_players: string[]
}

function Names({ title, names }: { title: string; names?: string[] }) {
  if (!names?.length) return null
  return (
    <details>
      <summary>
        {title} ({names.length})
      </summary>
      <p>{names.join(', ')}</p>
    </details>
  )
}

/** What an import did, or (preview) would do. */
function ImportReport({ report }: { report: Report }) {
  const will = report.preview
  return (
    <>
      <p>
        {will ? 'This file would add' : 'Added'} {report.added}, {will ? 'update' : 'updated'} {report.updated}, leave {report.unchanged}{' '}
        unchanged and {will ? 'switch off' : 'switched off'} {report.deactivated}.
      </p>
      <Names title="New players" names={report.added_names} />
      <Names title="Updated players" names={report.updated_names} />
      <Names title="Center changes" names={report.center_changes} />
      <Names title={will ? 'Would be switched off (not in the file)' : 'Switched off (not in the file)'} names={report.deactivated_names} />
      {(report.no_center?.length ?? 0) > 0 && (
        <p>
          {NO_CENTER}: {report.no_center!.join(', ')}. Set their center below, or team them up in Teams.
        </p>
      )}
      {(report.no_email?.length ?? 0) > 0 && (
        <p>No email on file (they can't create their own account; use Set login): {report.no_email!.join(', ')}.</p>
      )}
      {report.skipped.length > 0 && <p>Skipped rows: {report.skipped.map((s) => `${s.row} (${s.reason})`).join(', ')}</p>}
      {report.possible_duplicates.length > 0 && <p>Same name at one center (check they are different people): {report.possible_duplicates.join(', ')}</p>}
      {report.teams_with_removed_players.length > 0 && <p>Teams with removed players: {report.teams_with_removed_players.join(', ')}</p>}
    </>
  )
}

function Center({ player, onChange }: { player: AdminPlayer; onChange: () => void }) {
  const { run, message } = useAction()
  const [open, setOpen] = useState(false)
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const center = String(new FormData(event.currentTarget).get('center') ?? '')
    if (await run(`/admin/players/${player.id}`, 'PATCH', { center }, () => 'Center saved')) {
      setOpen(false)
      onChange()
    }
  }
  const missing = !player.center
  return (
    <div className="stack" style={{ margin: 0, gap: '0.3rem' }}>
      {open ? (
        <form className="inline-form" onSubmit={save} aria-label={`Center for ${player.first_name} ${player.last_name}`}>
          <input name="center" defaultValue={missing ? '' : player.center} aria-label="Center" required maxLength={60} />
          <button type="submit">Save</button>
          <button type="button" className="link" onClick={() => setOpen(false)}>Cancel</button>
        </form>
      ) : (
        <span>
          {missing ? <span className="warning-text">{NO_CENTER}</span> : player.center}{' '}
          <button type="button" className="link" onClick={() => setOpen(true)} aria-label={`Edit center for ${player.first_name} ${player.last_name}`}>
            Edit
          </button>
        </span>
      )}
      <Message message={message} />
    </div>
  )
}

function Account({ player, onChange }: { player: AdminPlayer; onChange: () => void }) {
  const { run, message } = useAction()
  const [open, setOpen] = useState(false)
  const url = `/admin/players/${player.id}/login`
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = { username: form.get('username') || null, password: form.get('password') || null }
    if (await run(url, 'PUT', body, () => 'Login saved. The password is temporary.')) {
      setOpen(false)
      onChange()
    }
  }
  const release = async () => {
    if (window.confirm(`Release ${player.first_name}'s account? They can create it again.`) && (await run(url, 'DELETE', undefined, () => 'Account released'))) onChange()
  }
  return (
    <div className="stack" style={{ margin: 0, gap: '0.3rem' }}>
      <span>
        {player.username ?? <span className="muted">No account{player.has_email === false && ' · no email on file'}</span>}
        {player.must_change_password && <small className="muted"> · temporary password</small>}
      </span>
      {open ? (
        <form className="inline-form" onSubmit={save} aria-label={`Login for ${player.first_name} ${player.last_name}`}>
          <input name="username" defaultValue={player.username ?? ''} placeholder="username" aria-label="Username" autoCapitalize="none" />
          <input name="password" placeholder="temporary password" aria-label="Temporary password" autoComplete="off" minLength={6} />
          <button type="submit">Save</button>
          <button type="button" className="link" onClick={() => setOpen(false)}>Cancel</button>
        </form>
      ) : (
        <div className="toolbar">
          <button type="button" className="link" onClick={() => setOpen(true)}>Set login</button>
          {player.username && <button type="button" className="link danger" onClick={release}>Release</button>}
        </div>
      )}
      <Message message={message} />
    </div>
  )
}

export default function Players() {
  const { token, message, setMessage } = useAction()
  const { data, loading, error, reload } = useApi<AdminPlayer[]>('/admin/players', token)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Report | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [filter, setFilter] = useState('')
  const send = async (asPreview: boolean): Promise<Report | null> => {
    const form = new FormData()
    form.append('file', file!)
    try {
      const answer = await api<Report>(`/admin/players/import${asPreview ? '?preview=true' : ''}`, { method: 'POST', form, token })
      setMessage(null)
      return answer
    } catch (e) {
      setMessage({ ok: false, text: (e as ApiError).message })
      return null
    }
  }
  // two steps: check the file (nothing changes), then import what the check showed
  const check = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) {
      setMessage({ ok: false, text: 'Choose the registration export first' })
      return
    }
    setReport(null)
    setPreview(await send(true))
  }
  const confirm = async () => {
    const done = await send(false)
    if (done) {
      setPreview(null)
      setReport(done)
      reload()
    }
  }
  const shown = (data ?? []).filter((p) =>
    `${p.first_name} ${p.last_name} ${p.center} ${p.email ?? ''} ${p.card_name ?? ''} ${p.mis_id} ${p.baps_id ?? ''}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  )
  return (
    <>
      <form onSubmit={check} className="stack">
        <h2>Import registrations</h2>
        <p className="hint">
          Upload the registration export (.xlsx or .csv); every column is kept. Players are recognised by first name, last name and email,
          and create their account with them. Rows without an email are matched by name and center. You see every change before it is
          saved, and nobody is deleted.
        </p>
        <input
          name="file"
          type="file"
          accept=".xlsx,.csv"
          aria-label="Registration file"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null)
            setPreview(null)
          }}
        />
        <button type="submit">Check file</button>
      </form>
      <Message message={message} />
      {preview && (
        <div role="status" className="card" aria-label="Import preview">
          <h3>Nothing changed yet</h3>
          <ImportReport report={preview} />
          <div className="toolbar">
            <button type="button" onClick={confirm}>
              Import these changes
            </button>
            <button type="button" className="link" onClick={() => setPreview(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {report && (
        <div role="status" className="card" aria-label="Import result">
          <ImportReport report={report} />
        </div>
      )}
      <h2>Players ({data?.length ?? 0})</h2>
      <input placeholder="Search name, center, email or ID" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Search players" />
      <Status loading={loading} error={error} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Center</th>
              <th>Email</th>
              <th>ID</th>
              <th>Registered</th>
              <th>Shirt</th>
              <th>Team</th>
              <th>Account</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p) => (
              <tr key={p.id} className={p.active ? '' : 'inactive'}>
                <td>
                  {p.first_name} {p.last_name}
                  {p.active ? '' : ' (removed)'}
                </td>
                <td>
                  <Center player={p} onChange={reload} />
                </td>
                <td>
                  {p.email || <span className="muted">none</span>}
                  {p.card_name && p.card_name.toLowerCase() !== `${p.first_name} ${p.last_name}`.toLowerCase() && (
                    <small className="muted"> · card: {p.card_name}</small>
                  )}
                </td>
                <td>{p.mis_id || p.baps_id}</td>
                <td>{p.registered_at}</td>
                <td>{p.tshirt_size}</td>
                <td>{p.team?.name ?? '-'}</td>
                <td>
                  <Account player={p} onChange={reload} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
