import { useState, type FormEvent } from 'react'

import { teamLabel } from '../../components/MatchCard'
import Status from '../../components/Status'
import { time } from '../../lib/format'
import { useApi } from '../../lib/live'
import type { Match } from '../../lib/types'
import { Message, useAction } from './common'

const REASONS = ['reached_11', 'clock_lead', 'sudden_death', 'forfeit']

export default function Results() {
  const { run, message } = useAction()
  const { data, loading, error, reload } = useApi<Match[]>('/public/schedule')
  const [editing, setEditing] = useState<number | null>(null)
  const played = (data ?? []).filter((m) => m.status === 'completed' || m.status === 'in_progress')
  const correct = async (event: FormEvent<HTMLFormElement>, match: Match) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = {
      score_a: Number(form.get('score_a')),
      score_b: Number(form.get('score_b')),
      end_reason: form.get('end_reason'),
      reason: form.get('reason'),
    }
    const result = await run<Match>(`/admin/matches/${match.id}/correct`, 'POST', body, (r) =>
      `${match.code} corrected.${r.warnings?.length ? ` Check: ${r.warnings.join('; ')}` : ''}`,
    )
    if (result) {
      setEditing(null)
      reload()
    }
  }
  const reset = async (match: Match) => {
    const reason = window.prompt(`Why reset ${match.code} to not started?`)
    if (reason && (await run(`/admin/matches/${match.id}/reset`, 'POST', { reason }, () => `${match.code} reset`))) reload()
  }
  return (
    <>
      <Message message={message} />
      <Status loading={loading} error={error} />
      {played.length === 0 && <p>No games played yet.</p>}
      <table>
        <thead>
          <tr><th>Time</th><th>Game</th><th>Result</th><th /></tr>
        </thead>
        <tbody>
          {played.map((m) => (
            <tr key={m.id}>
              <td>{time(m.scheduled_at)}</td>
              <td>{m.code} · court {m.court}</td>
              <td>
                {editing === m.id ? (
                  <form onSubmit={(e) => correct(e, m)} className="inline-form" aria-label={`Correct ${m.code}`}>
                    <input name="score_a" type="number" min={0} max={12} defaultValue={m.score_a ?? 0} aria-label={`${teamLabel(m.team_a, null)} score`} />
                    <input name="score_b" type="number" min={0} max={12} defaultValue={m.score_b ?? 0} aria-label={`${teamLabel(m.team_b, null)} score`} />
                    <select name="end_reason" defaultValue={m.end_reason ?? 'reached_11'} aria-label="How it ended">
                      {REASONS.map((r) => <option key={r}>{r}</option>)}
                    </select>
                    <input name="reason" required placeholder="Why" aria-label="Reason" />
                    <button type="submit">Save</button>
                    <button type="button" className="link" onClick={() => setEditing(null)}>Cancel</button>
                  </form>
                ) : (
                  <>
                    {teamLabel(m.team_a, m.source_a)} {m.score_a} - {m.score_b} {teamLabel(m.team_b, m.source_b)}{' '}
                    <small>{m.status === 'in_progress' ? 'live' : m.end_reason}</small>
                  </>
                )}
              </td>
              <td>
                {m.status === 'completed' && editing !== m.id && (
                  <button type="button" className="link" onClick={() => setEditing(m.id)}>Correct</button>
                )}
                <button type="button" className="link danger" onClick={() => reset(m)}>Reset</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
