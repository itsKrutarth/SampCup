import { useEffect, useState, useSyncExternalStore } from 'react'
import { Navigate, useSearchParams } from 'react-router'

import { teamLabel } from '../components/MatchCard'
import Status from '../components/Status'
import { useAuth } from '../lib/auth'
import { clock, time } from '../lib/format'
import { useApi } from '../lib/live'
import { judgeQueue, type Action } from '../lib/queue'
import type { Match } from '../lib/types'

const GAME_SECONDS = 12 * 60

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

type Send = (action: Action, body?: Record<string, unknown>) => void

function Timer({ startedAt }: { startedAt: number }) {
  const now = useNow()
  const left = GAME_SECONDS - (now - startedAt) / 1000
  return (
    <p className={left <= 0 ? 'timer done' : 'timer'} aria-label="Time left">
      {left > 0 ? clock(left) : 'Time!'}
    </p>
  )
}

export function ScoreCard({ match, send }: { match: Match; send: Send }) {
  const [scores, setScores] = useState<[number, number]>([match.score_a ?? 0, match.score_b ?? 0])
  const [startedAt, setStartedAt] = useState<number | null>(
    match.started_at ? Date.parse(match.started_at) : null,
  )
  const [step, setStep] = useState<'play' | 'sudden' | 'forfeit' | 'sent'>('play')
  const [a, b] = scores
  const names = [teamLabel(match.team_a, match.source_a), teamLabel(match.team_b, match.source_b)]

  const change = (side: 0 | 1, delta: number) => {
    const next: [number, number] = [a, b]
    next[side] = Math.min(11, Math.max(0, next[side] + delta))
    setScores(next)
    send('score', { score_a: next[0], score_b: next[1] })
  }
  const finish = (end_reason: string, extra: Record<string, unknown> = {}) => {
    send('finish', { score_a: a, score_b: b, end_reason, ...extra })
    setStep('sent')
  }

  if (step === 'sent') return <p role="status" className="success">Result sent. The next game loads when it is confirmed.</p>
  if (startedAt === null) {
    return (
      <section className="scorecard" aria-label="Current game">
        <h2>
          {match.round} · {time(match.scheduled_at)}
        </h2>
        <p className="versus">
          {names[0]} <span>vs</span> {names[1]}
        </p>
        <button
          type="button"
          className="big"
          onClick={() => {
            setStartedAt(Date.now())
            send('start')
          }}
        >
          Start game
        </button>
        <ForfeitButtons names={names} send={send} onDone={() => setStep('sent')} />
      </section>
    )
  }
  return (
    <section className="scorecard" aria-label="Current game">
      <h2>{match.round}</h2>
      <Timer startedAt={startedAt} />
      <div className="scores">
        {([0, 1] as const).map((side) => (
          <div key={side} className="team-score">
            <p>{names[side]}</p>
            <p className="big-score" aria-label={`${names[side]} score`}>
              {scores[side]}
            </p>
            <button type="button" className="big" aria-label={`Point to ${names[side]}`} onClick={() => change(side, 1)} disabled={scores[side] >= 11}>
              +1
            </button>
            <button type="button" className="secondary" aria-label={`Take a point from ${names[side]}`} onClick={() => change(side, -1)} disabled={scores[side] <= 0}>
              −1
            </button>
          </div>
        ))}
      </div>
      {step === 'sudden' ? (
        <div className="stack">
          <p>Tied when the clock ended. Who won the sudden-death point?</p>
          <button type="button" onClick={() => finish('clock_lead', { sudden_death_winner: 'a' })}>
            {names[0]}
          </button>
          <button type="button" onClick={() => finish('clock_lead', { sudden_death_winner: 'b' })}>
            {names[1]}
          </button>
          <button type="button" className="link" onClick={() => setStep('play')}>
            Back
          </button>
        </div>
      ) : (
        <div className="stack">
          <button type="button" disabled={Math.max(a, b) !== 11 || a === b} onClick={() => finish('reached_11')}>
            Final: reached 11
          </button>
          <button type="button" className="secondary" onClick={() => (a === b ? setStep('sudden') : finish('clock_lead'))}>
            Clock ended
          </button>
          <ForfeitButtons names={names} send={send} onDone={() => setStep('sent')} />
        </div>
      )}
    </section>
  )
}

function ForfeitButtons({ names, send, onDone }: { names: string[]; send: Send; onDone: () => void }) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" className="link" onClick={() => setOpen(true)}>
        Forfeit…
      </button>
    )
  }
  const pick = (winner: 'a' | 'b') => {
    send('forfeit', { winner })
    onDone()
  }
  return (
    <div className="stack">
      <p>Which team wins by forfeit (11-0)?</p>
      <button type="button" onClick={() => pick('a')}>{names[0]} wins</button>
      <button type="button" onClick={() => pick('b')}>{names[1]} wins</button>
      <button type="button" className="link" onClick={() => setOpen(false)}>Cancel</button>
    </div>
  )
}

export default function Judge() {
  const { auth, signOut } = useAuth()
  const [params, setParams] = useSearchParams()
  const token = auth?.kind === 'staff' ? auth.token : null
  const fixedCourt = auth?.role === 'judge' ? auth.court : null
  const court = fixedCourt ?? (Number(params.get('court')) || null)
  const path = court ? `/judge/matches?court=${court}` : '/judge/matches'
  const { data, loading, error, reload } = useApi<{ court: number | null; current: Match | null; matches: Match[] }>(
    token ? path : null,
    token,
  )
  const queue = useSyncExternalStore(judgeQueue.subscribe, judgeQueue.getState)

  useEffect(() => {
    judgeQueue.token = token
    judgeQueue.onSent = (match) => {
      if (match.status === 'completed' || match.status === 'cancelled') reload()
    }
    const retry = () => void judgeQueue.flush()
    retry()
    const id = setInterval(retry, 5000)
    window.addEventListener('online', retry)
    return () => {
      clearInterval(id)
      window.removeEventListener('online', retry)
      judgeQueue.onSent = null
    }
  }, [token, reload])

  if (!token) return <Navigate to="/staff" replace />
  const upcoming = data?.matches.filter((m) => m.status === 'scheduled' && m.id !== data.current?.id) ?? []
  return (
    <>
      <header className="judge-head">
        <h1>{court ? `Court ${court}` : 'Judge'}</h1>
        <span>{auth?.name}</span>
        <button type="button" className="link" onClick={signOut}>
          Log out
        </button>
      </header>
      {!fixedCourt && (
        <label>
          Court
          <select
            value={court ?? ''}
            onChange={(e) => setParams(e.target.value ? { court: e.target.value } : {})}
          >
            <option value="">Choose a court</option>
            {Array.from({ length: 9 }, (_, i) => (
              <option key={i + 1}>{i + 1}</option>
            ))}
          </select>
        </label>
      )}
      {queue.pending > 0 && <p role="status" className="warning">{queue.pending} update(s) waiting to send</p>}
      {queue.error && <p role="alert" className="error">{queue.error}</p>}
      <Status loading={loading} error={error} />
      {data && !data.current && <p>No game is ready on this court right now.</p>}
      {data?.current && (
        <ScoreCard
          key={data.current.id}
          match={data.current}
          send={(action, body) => void judgeQueue.push({ matchId: data.current!.id, action, body })}
        />
      )}
      {upcoming.length > 0 && (
        <section aria-label="Later on this court">
          <h2>Later on this court</h2>
          <ul className="plain">
            {upcoming.slice(0, 6).map((m) => (
              <li key={m.id}>
                {time(m.scheduled_at)} · {teamLabel(m.team_a, m.source_a)} vs {teamLabel(m.team_b, m.source_b)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
