import { ArrowLeft, Building2, Check, Handshake, PartyPopper, Send, UserRound, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import Status from '../components/Status'
import { api, ApiError } from '../lib/api'
import { useApi } from '../lib/live'
import type { PartnerRequest, PlayerLite, TeamOut } from '../lib/types'

type PlayerStatus = {
  player: PlayerLite
  team: TeamOut | null
  incoming: PartnerRequest[]
  outgoing: PartnerRequest | null
}

const fullName = (p: PlayerLite) => `${p.first_name} ${p.last_name}`

function Centers({ onPick }: { onPick: (center: string) => void }) {
  const { data, loading, error } = useApi<{ center: string; players: number }[]>('/registration/centers')
  return (
    <>
      <h2>1. Your center</h2>
      <p className="hint">Pick the center you registered with.</p>
      <Status loading={loading} error={error} />
      {data?.length === 0 && <p>Registrations have not been loaded yet. Check back soon.</p>}
      <div className="choices">
        {data?.map((c) => (
          <button key={c.center} type="button" onClick={() => onPick(c.center)}>
            <Building2 size={22} />
            <span>
              {c.center}
              <small>{c.players} players</small>
            </span>
          </button>
        ))}
      </div>
    </>
  )
}

function WhoAreYou({ center, onPick }: { center: string; onPick: (id: number) => void }) {
  const { data, loading, error } = useApi<PlayerLite[]>(`/registration/players?center=${encodeURIComponent(center)}`)
  return (
    <>
      <h2>2. Who are you?</h2>
      <p className="hint">Tap your name.</p>
      <Status loading={loading} error={error} />
      <div className="choices">
        {data?.map((p) => (
          <button key={p.id} type="button" onClick={() => onPick(p.id)}>
            <UserRound size={22} />
            <span>
              {fullName(p)}
              <small>
                {p.zone}
                {p.state === 'teamed' && ` · ${p.team_name}`}
              </small>
            </span>
            <span className={`state ${p.state}`}>{p.state === 'teamed' ? 'On a team' : p.state === 'pending' ? 'Pending' : 'Free'}</span>
          </button>
        ))}
      </div>
    </>
  )
}

function PartnerForm({ me, onSent }: { me: PlayerLite; onSent: () => void }) {
  const { data } = useApi<PlayerLite[]>(`/registration/players?center=${encodeURIComponent(me.center)}`)
  const [error, setError] = useState('')
  const partners = data?.filter((p) => p.id !== me.id && p.state !== 'teamed') ?? []
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    if (form.get('password') !== form.get('confirm')) {
      setError('The two passwords do not match')
      return
    }
    try {
      await api('/registration/requests', {
        method: 'POST',
        body: {
          from_player_id: me.id,
          to_player_id: Number(form.get('partner')),
          team_name: form.get('team_name'),
          password: form.get('password'),
        },
      })
      onSent()
    } catch (e) {
      setError((e as ApiError).message)
    }
  }
  return (
    <form onSubmit={submit} className="stack card">
      <h2>3. Pick your partner</h2>
      <p className="hint">Your partner must be from {me.center}. Once they accept, only an admin can change the team.</p>
      <label>
        Partner
        <select name="partner" required defaultValue="">
          <option value="" disabled>
            Choose…
          </option>
          {partners.map((p) => (
            <option key={p.id} value={p.id}>
              {fullName(p)} ({p.zone}){p.state === 'pending' ? ' · has a pending request' : ''}
            </option>
          ))}
        </select>
      </label>
      <label>
        Team name
        <input name="team_name" required minLength={2} maxLength={40} />
      </label>
      <label>
        Team password
        <input name="password" type="password" required minLength={4} maxLength={72} autoComplete="new-password" />
      </label>
      <label>
        Password again
        <input name="confirm" type="password" required autoComplete="new-password" />
      </label>
      <p className="hint">You and your partner log in with the team name and this password. Share it with your partner.</p>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit">
        <Send size={18} />
        Send request
      </button>
    </form>
  )
}

function MyStatus({ playerId }: { playerId: number }) {
  const { data, loading, error, reload } = useApi<PlayerStatus>(`/registration/players/${playerId}`)
  const [message, setMessage] = useState('')
  const [actionError, setActionError] = useState('')
  if (!data) return <Status loading={loading} error={error} />
  const respond = async (request: PartnerRequest, action: 'accept' | 'decline' | 'cancel') => {
    try {
      await api(`/registration/requests/${request.id}/${action}`, { method: 'POST', body: { player_id: playerId } })
      setActionError('')
      setMessage(
        action === 'accept'
          ? `Team ${request.team_name} is ready. Log in with the team name and the password ${fullName(request.from)} chose.`
          : '',
      )
      reload()
    } catch (e) {
      setActionError((e as ApiError).message)
    }
  }
  const { player, team, incoming, outgoing } = data
  return (
    <>
      <p>
        Hi <strong>{player.first_name}</strong>.
      </p>
      {message && (
        <p role="status" className="success">
          <PartyPopper size={20} />
          {message}
        </p>
      )}
      {actionError && <p role="alert" className="error">{actionError}</p>}
      {team ? (
        <section className="card">
          <h2>
            <Handshake size={22} /> Your team: {team.name}
          </h2>
          <p>{team.players.map((p) => p.name).join(' & ')}</p>
          {team.status === 'waitlist' && <p>The tournament is full, so your team is on the waitlist. An admin will let you know.</p>}
          <Link className="button" to="/login">
            Team login
          </Link>
        </section>
      ) : (
        <>
          {incoming.map((r) => (
            <section key={r.id} className="card">
              <p>
                <strong>{fullName(r.from)}</strong> wants to team up as <strong>{r.team_name}</strong>.
              </p>
              <div className="toolbar">
                <button type="button" onClick={() => respond(r, 'accept')}>
                  <Check size={18} />
                  Accept
                </button>
                <button type="button" className="secondary" onClick={() => respond(r, 'decline')}>
                  <X size={18} />
                  Decline
                </button>
              </div>
            </section>
          ))}
          {outgoing ? (
            <section className="card">
              <p>
                Waiting for <strong>{fullName(outgoing.to)}</strong> to accept <strong>{outgoing.team_name}</strong>.
              </p>
              <button type="button" className="secondary" onClick={() => respond(outgoing, 'cancel')}>
                Cancel request
              </button>
            </section>
          ) : (
            <PartnerForm me={player} onSent={reload} />
          )}
        </>
      )}
    </>
  )
}

export default function Join() {
  const [params, setParams] = useSearchParams()
  const status = useApi<{ open: boolean }>('/registration/status')
  const center = params.get('center')
  const me = Number(params.get('me')) || null
  const go = (next: Record<string, string>) => setParams(next)
  const step = me ? 3 : center ? 2 : 1
  return (
    <>
      <h1>Join SAMP Cup</h1>
      <ol className="stepper" aria-label="Steps">
        {['Center', 'You', 'Partner'].map((label, i) => (
          <li key={label} className={i + 1 < step ? 'done' : i + 1 === step ? 'current' : ''}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>
      {status.data && !status.data.open && (
        <p role="alert" className="error">Team registration is closed. Ask an admin if you need a change.</p>
      )}
      {(center || me) && (
        <button type="button" className="link" aria-label="← Back" onClick={() => go(me && center ? { center } : {})}>
          <ArrowLeft size={16} /> Back
        </button>
      )}
      {!center && <Centers onPick={(c) => go({ center: c })} />}
      {center && !me && <WhoAreYou center={center} onPick={(id) => go({ center, me: String(id) })} />}
      {me && <MyStatus playerId={me} />}
    </>
  )
}
