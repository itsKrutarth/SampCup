import type { FormEvent } from 'react'

import Status from '../../components/Status'
import { useApi } from '../../lib/live'
import type { PartnerRequest, TeamOut } from '../../lib/types'
import { Message, useAction } from './common'
import type { AdminPlayer } from './Players'

export default function Teams() {
  const { token, run, message } = useAction()
  const teams = useApi<TeamOut[]>('/admin/teams', token)
  const players = useApi<AdminPlayer[]>('/admin/players', token)
  const requests = useApi<PartnerRequest[]>('/admin/requests', token)
  const free = (players.data ?? []).filter((p) => p.active && !p.team)
  const refresh = () => {
    teams.reload()
    players.reload()
    requests.reload()
  }
  const patch = async (team: TeamOut, body: Record<string, unknown>, text: string) => {
    if (await run(`/admin/teams/${team.id}`, 'PATCH', body, () => text)) refresh()
  }
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = {
      name: form.get('name'),
      password: form.get('password'),
      player_ids: [Number(form.get('player_a')), Number(form.get('player_b'))],
    }
    if (await run('/admin/teams', 'POST', body, () => `Team ${body.name} created`)) {
      event.currentTarget?.reset()
      refresh()
    }
  }
  return (
    <>
      <Message message={message} />
      <Status loading={teams.loading} error={teams.error} />
      <h2>Teams ({teams.data?.length ?? 0})</h2>
      <table>
        <thead>
          <tr><th>#</th><th>Team</th><th>Players</th><th>Status</th><th>Here</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {teams.data?.map((t) => (
            <tr key={t.id}>
              <td>{t.number ?? ''}</td>
              <td>{t.name}<br /><small>{t.center}</small></td>
              <td>{t.players.map((p) => p.name).join(' & ')}</td>
              <td>
                <select aria-label={`Status of ${t.name}`} value={t.status} onChange={(e) => patch(t, { status: e.target.value }, `${t.name} is now ${e.target.value}`)}>
                  <option value="active">active</option>
                  <option value="waitlist">waitlist</option>
                  <option value="withdrawn">withdrawn</option>
                </select>
              </td>
              <td>
                <input type="checkbox" aria-label={`${t.name} checked in`} checked={Boolean(t.checked_in)} onChange={(e) => patch(t, { checked_in: e.target.checked }, `${t.name} ${e.target.checked ? 'checked in' : 'not checked in'}`)} />
              </td>
              <td>
                <button type="button" className="link" onClick={() => {
                  const password = window.prompt(`New password for ${t.name}`)
                  if (password) void patch(t, { password }, `Password changed for ${t.name}`)
                }}>
                  Reset password
                </button>
                <button type="button" className="link danger" onClick={async () => {
                  if (window.confirm(`Delete team ${t.name}? Its players become free.`) && (await run(`/admin/teams/${t.id}`, 'DELETE', undefined, () => `${t.name} deleted`)) !== undefined) refresh()
                }}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={create} className="stack">
        <h2>Make a team</h2>
        <p className="hint">Admins can pair any two players who are not on a team.</p>
        <label>Team name<input name="name" required minLength={2} maxLength={40} /></label>
        <label>Password<input name="password" required minLength={4} /></label>
        {(['player_a', 'player_b'] as const).map((field, i) => (
          <label key={field}>
            Player {i + 1}
            <select name={field} required defaultValue="">
              <option value="" disabled>Choose…</option>
              {free.map((p) => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.center})</option>
              ))}
            </select>
          </label>
        ))}
        <button type="submit">Create team</button>
      </form>
      <h2>Waiting partner requests</h2>
      {requests.data?.length === 0 && <p>None.</p>}
      <ul className="plain">
        {requests.data?.map((r) => (
          <li key={r.id}>
            {r.from.first_name} {r.from.last_name} → {r.to.first_name} {r.to.last_name}: {r.team_name}{' '}
            <button type="button" className="link" onClick={async () => {
              if (await run(`/admin/requests/${r.id}/cancel`, 'POST', undefined, () => 'Request cancelled')) refresh()
            }}>
              Cancel
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}
