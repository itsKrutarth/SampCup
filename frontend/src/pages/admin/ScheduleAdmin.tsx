import type { FormEvent } from 'react'

import { teamLabel } from '../../components/MatchCard'
import Status from '../../components/Status'
import { time, venueTimeToIso } from '../../lib/format'
import { useApi } from '../../lib/live'
import type { Match } from '../../lib/types'
import { Message, useAction } from './common'
import type { Summary } from './Overview'

type DelayResult = { moved: number; warnings: string[] }

export default function ScheduleAdmin() {
  const { token, run, message } = useAction()
  const summary = useApi<Summary>('/admin/summary', token)
  const matches = useApi<Match[]>('/public/schedule')
  const t = summary.data?.tournament
  const refresh = () => {
    summary.reload()
    matches.reload()
  }
  const act = async (path: string, method: string, body: unknown, text: (r: never) => string) => {
    if ((await run(path, method, body, text)) !== undefined) refresh()
  }
  const delay = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = {
      minutes: Number(form.get('minutes')),
      from_time: venueTimeToIso(t?.event_date ?? '', String(form.get('from'))),
    }
    await act('/admin/delays', 'POST', body, (r: DelayResult) =>
      `Moved ${r.moved} games.${r.warnings.length ? ` Check: ${r.warnings.join('; ')}` : ''}`,
    )
  }
  if (!t) return <Status loading={summary.loading} error={summary.error} />
  return (
    <>
      <Message message={message} />
      <ol className="steps">
        <li>Check in the teams that are here (Teams tab). The draw uses checked-in active teams (32-42).</li>
        <li>
          <button type="button" disabled={t.schedule_exists} onClick={() => act('/admin/draw', 'POST', {}, (r: unknown[]) => `Drew numbers for ${r.length} teams`)}>
            Draw team numbers
          </button>
        </li>
        <li>
          <button type="button" disabled={t.schedule_locked} onClick={() => act('/admin/schedule', 'POST', undefined, (r: { matches: number }) => `Schedule ready: ${r.matches} games`)}>
            Generate schedule
          </button>
        </li>
        <li>
          <button type="button" disabled={!t.schedule_exists} onClick={() => act('/admin/schedule/lock', 'POST', { locked: !t.schedule_locked }, () => (t.schedule_locked ? 'Schedule unlocked' : 'Schedule locked'))}>
            {t.schedule_locked ? 'Unlock schedule' : 'Lock schedule'}
          </button>{' '}
          <button type="button" className="secondary" disabled={!t.schedule_exists || t.schedule_locked} onClick={() => {
            if (window.confirm('Delete the whole schedule? Team numbers stay.')) void act('/admin/schedule', 'DELETE', undefined, () => 'Schedule cleared')
          }}>
            Clear schedule
          </button>
        </li>
      </ol>
      <form onSubmit={delay} className="stack">
        <h2>Running behind</h2>
        <p className="hint">Moves every game that has not started, from this time on.</p>
        <label>From (venue time)<input name="from" type="time" required /></label>
        <label>Minutes (negative to pull earlier)<input name="minutes" type="number" min={-60} max={120} required /></label>
        <button type="submit" disabled={!t.schedule_exists}>Shift games</button>
      </form>
      <h2>Games</h2>
      <Status loading={matches.loading} error={matches.error} />
      <table>
        <thead>
          <tr><th>Time</th><th>Game</th><th>Teams</th><th>Court</th></tr>
        </thead>
        <tbody>
          {matches.data?.map((m) => (
            <tr key={m.id}>
              <td>{time(m.scheduled_at)}</td>
              <td>{m.code}</td>
              <td>{teamLabel(m.team_a, m.source_a)} vs {teamLabel(m.team_b, m.source_b)}</td>
              <td>
                <select aria-label={`Court for ${m.code}`} value={m.court} disabled={m.status === 'completed' || m.status === 'cancelled'} onChange={(e) => {
                  const court = Number(e.target.value)
                  void act(`/admin/matches/${m.id}`, 'PATCH', { court }, () => `${m.code} moved to court ${court}`)
                }}>
                  {Array.from({ length: 9 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
