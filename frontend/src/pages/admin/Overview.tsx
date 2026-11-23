import { CalendarCheck, Download, ExternalLink, ListChecks, Save, Sheet, Shirt, UserCheck, Users, UsersRound } from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'

import Status from '../../components/Status'
import { download } from '../../lib/api'
import { useApi } from '../../lib/live'
import { Message, useAction } from './common'

export type Summary = {
  tournament: {
    name: string
    subtitle: string
    venue_name: string
    venue_address: string
    age_group: string
    contacts: string
    event_date: string | null
    registration_open: boolean
    team_cap: number
    draw_seed: number | null
    schedule_locked: boolean
    schedule_exists: boolean
    backup_sheet_url?: string
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
      subtitle: form.get('subtitle'),
      venue_name: form.get('venue_name'),
      venue_address: form.get('venue_address'),
      age_group: form.get('age_group'),
      contacts: form.get('contacts'),
      registration_open: form.get('registration_open') === 'on',
      team_cap: Number(form.get('team_cap')),
      backup_sheet_url: String(form.get('backup_sheet_url') ?? '').trim(),
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
      <section className="card backup-sheet" aria-label="Backup sheet">
        <h2>
          <Sheet size={20} /> Backup sheet
        </h2>
        {t.backup_sheet_url ? (
          <>
            <p>A copy of the whole tournament, updated every minute. If the app goes down, run the day from it.</p>
            <a className="button" href={t.backup_sheet_url} target="_blank" rel="noreferrer">
              <ExternalLink size={18} />
              Open the backup sheet
            </a>
          </>
        ) : (
          <p>Not linked yet. Set the sheet up once (tools/backup-sheet/README.md), then paste its address below in Settings.</p>
        )}
      </section>
      <form onSubmit={save} className="stack card" key={JSON.stringify(t)}>
        <h2>Settings</h2>
        <label>
          Tournament name
          <input name="name" defaultValue={t.name} required minLength={2} />
        </label>
        <label>
          Subtitle (red ribbon)
          <input name="subtitle" defaultValue={t.subtitle} maxLength={80} />
        </label>
        <label>
          Venue
          <input name="venue_name" defaultValue={t.venue_name} maxLength={80} />
        </label>
        <label>
          Venue address
          <input name="venue_address" defaultValue={t.venue_address} maxLength={160} />
        </label>
        <label>
          Age group
          <input name="age_group" defaultValue={t.age_group} maxLength={20} />
        </label>
        <label>
          Contacts on the home page
          <textarea name="contacts" defaultValue={t.contacts} maxLength={500} rows={3} placeholder="Name (phone)" />
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
        <label>
          Backup sheet address (Google Sheets)
          <input
            name="backup_sheet_url"
            type="url"
            defaultValue={t.backup_sheet_url ?? ''}
            maxLength={300}
            pattern="https://docs\.google\.com/spreadsheets/.*"
            placeholder="https://docs.google.com/spreadsheets/d/..."
          />
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
