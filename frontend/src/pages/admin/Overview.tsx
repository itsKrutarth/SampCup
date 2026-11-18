import { CalendarCheck, Download, ListChecks, Save, Shirt, UserCheck, Users, UsersRound } from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'

import Status from '../../components/Status'
import { download } from '../../lib/api'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

export type Summary = {
  tournament: {
    name: string
    event_date: string | null
    registration_open: boolean
    team_cap: number
    draw_seed: number | null
    schedule_locked: boolean
    schedule_exists: boolean
  }
  players: number
  players_on_teams: number
  teams: { active: number; waitlist: number; withdrawn: number }
  checked_in: number
  pending_requests: number
  tshirts: Record<string, number>
}

function Stat({ icon, value, label }: { icon: ReactNode; value: ReactNode; label: string }) {
  return (
    <li className="stat">
      <span className="stat-icon">{icon}</span>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </li>
  )
}

export default function Overview() {
  const { token, run, message, setMessage } = useAction()
  const { data, loading, error, reload } = useApi<Summary>('/admin/summary', token)
  if (!data) return <Status loading={loading} error={error} />
  const t = data.tournament
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body: Record<string, unknown> = {
      name: form.get('name'),
      registration_open: form.get('registration_open') === 'on',
      team_cap: Number(form.get('team_cap')),
    }
    if (form.get('event_date') && form.get('event_date') !== t.event_date) body.event_date = form.get('event_date')
    if (await run('/admin/tournament', 'PATCH', body, () => 'Settings saved')) reload()
  }
  return (
    <>
      <ul className="stats">
        <Stat icon={<Users size={20} />} value={data.players} label={`players (${data.players_on_teams} on teams)`} />
        <Stat
          icon={<UsersRound size={20} />}
          value={data.teams.active}
          label={`active teams, ${data.teams.waitlist} waitlist, ${data.teams.withdrawn} withdrawn`}
        />
        <Stat icon={<UserCheck size={20} />} value={data.checked_in} label="teams checked in" />
        <Stat icon={<ListChecks size={20} />} value={data.pending_requests} label="partner requests waiting" />
      </ul>
      <p className="info">
        <CalendarCheck size={18} />
        Schedule: {t.schedule_exists ? (t.schedule_locked ? 'locked' : 'generated, not locked') : 'not generated'}
        {t.draw_seed !== null && ` · Draw seed: ${t.draw_seed}`}
      </p>
      <form onSubmit={save} className="stack card" key={JSON.stringify(t)}>
        <h2>Settings</h2>
        <label>
          Tournament name
          <input name="name" defaultValue={t.name} required minLength={2} />
        </label>
        <label>
          Event date
          <input name="event_date" type="date" defaultValue={t.event_date ?? ''} />
        </label>
        <label>
          Team cap (32-42)
          <input name="team_cap" type="number" min={32} max={42} defaultValue={t.team_cap} />
        </label>
        <label className="inline">
          <input name="registration_open" type="checkbox" defaultChecked={t.registration_open} /> Players can form teams
        </label>
        <button type="submit">
          <Save size={18} />
          Save settings
        </button>
      </form>
      <Message message={message} />
      <h2>
        <Shirt size={20} /> T-shirts
      </h2>
      <p>{Object.entries(data.tshirts).map(([size, n]) => `${size}: ${n}`).join(' · ') || 'No players yet'}</p>
      <button
        type="button"
        className="secondary"
        onClick={() =>
          download('/admin/export/results.csv', token ?? '', 'sampcup-results.csv').catch((e: Error) =>
            setMessage({ ok: false, text: e.message }),
          )
        }
      >
        <Download size={18} />
        Download results (CSV)
      </button>
    </>
  )
}
