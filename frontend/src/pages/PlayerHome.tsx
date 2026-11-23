import { Check, Handshake, LogOut, PartyPopper, Send, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'

import Status from '../components/Status'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useApi } from '../lib/live'
import type { PartnerRequest, PlayerLite, TeamPage } from '../lib/types'
import { TeamDetails } from './TeamPage'

type Me = {
  player: PlayerLite
  team: TeamPage | null
  incoming: PartnerRequest[]
  outgoing: PartnerRequest | null
}

const fullName = (p: PlayerLite) => `${p.first_name} ${p.last_name}`

function PartnerForm({ me, token, onSent, invited }: { me: PlayerLite; token: string; onSent: () => void; invited: boolean }) {
  const { data } = useApi<PlayerLite[]>('/registration/players', token, 30_000)
  const [error, setError] = useState('')
  const partners = data?.filter((p) => p.state !== 'teamed') ?? []
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      await api('/registration/requests', {
        method: 'POST',
        token,
        body: { to_player_id: Number(form.get('partner')), team_name: form.get('team_name') },
      })
      onSent()
    } catch (e) {
      setError((e as ApiError).message)
    }
  }
  return (
    <form onSubmit={submit} className="stack card">
      <h2>{invited ? 'Or invite someone else' : 'Pick your partner'}</h2>
      <p className="hint">
        Your partner must be from {me.center}. They accept when they log in; after that only an admin can change the
        team.
      </p>
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
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit">
        <Send size={18} />
        Send invitation
      </button>
    </form>
  )
}

/**
 * Scores and the next game come from the public team page (cached by CloudFront), every 10s:
 * live rallies are on the home page's court board; this is for "when and where do we play".
 */
function LiveTeam({ team }: { team: TeamPage }) {
  const { data } = useApi<TeamPage>(team.number ? `/public/teams/${team.number}` : null, null, 10_000)
  return <TeamDetails team={data ?? team} />
}

/** A logged-in player's page: their team, or their invitations and the partner picker. */
export default function PlayerHome() {
  const { auth, signOut } = useAuth()
  const token = auth?.kind === 'player' ? auth.token : null
  // invitations and team changes are rare: check every 30s (and whenever the page comes back)
  const { data, loading, error, reload } = useApi<Me>(token ? '/player/me' : null, token, 30_000)
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [actionError, setActionError] = useState('')
  if (!token) return <Navigate to="/login" replace />
  if (auth?.mustChange) return <Navigate to="/account/password" replace />
  if (error?.status === 401 || error?.status === 403) {
    return (
      <>
        <p role="alert" className="error">Your login has expired.</p>
        <button type="button" onClick={signOut}>
          Log in again
        </button>
      </>
    )
  }
  const respond = async (request: PartnerRequest, action: 'accept' | 'decline' | 'cancel') => {
    try {
      await api(`/registration/requests/${request.id}/${action}`, { method: 'POST', token })
      setActionError('')
      setMessage(action === 'accept' ? `You're on ${request.team_name}!` : '')
      reload()
      if (action === 'accept') {
        // straight to the team view: no more picking partners
        navigate('/my-team', { replace: true })
        window.scrollTo?.({ top: 0 })
      }
    } catch (e) {
      setActionError((e as ApiError).message)
    }
  }
  const logout = (
    <button type="button" className="secondary" onClick={signOut}>
      <LogOut size={18} />
      Log out
    </button>
  )
  if (!data) return <Status loading={loading} error={error} />
  const { player, team, incoming, outgoing } = data
  return (
    <>
      <p className="tagline">
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
        <section aria-label="My team">
          <h2 className="eyebrow">My team</h2>
          <LiveTeam team={team} />
        </section>
      ) : (
        <>
          {incoming.map((r) => (
            <section key={r.id} className="card" aria-label={`Invitation to ${r.team_name}`}>
              <h2>
                <Handshake size={22} /> You're invited
              </h2>
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
                They'll see it when they log in.
              </p>
              <button type="button" className="secondary" onClick={() => respond(outgoing, 'cancel')}>
                Cancel invitation
              </button>
            </section>
          ) : (
            player.center ? (
              <PartnerForm me={player} token={token} onSent={reload} invited={incoming.length > 0} />
            ) : (
              <p className="info">
                Your registration has no center yet, so you can't pick a partner here. An admin will add your center or pair you
                up.
              </p>
            )
          )}
        </>
      )}
      {logout}
    </>
  )
}
