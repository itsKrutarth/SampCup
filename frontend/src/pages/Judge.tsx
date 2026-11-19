import { Clock3, Flag, Hourglass, LogOut, Minus, Play, Plus, Timer as TimerIcon, Wifi, WifiOff } from 'lucide-react'
import { useEffect, useState, useSyncExternalStore, type CSSProperties } from 'react'
import { Navigate, useSearchParams } from 'react-router'

import { teamLabel } from '../components/MatchCard'
import Status from '../components/Status'
import { useAuth } from '../lib/auth'
import { useNow } from '../lib/clock'
import { clock, time } from '../lib/format'
import { useApi } from '../lib/live'
import { judgeQueue, type Action } from '../lib/queue'
import type { Match } from '../lib/types'

const GAME_SECONDS = 12 * 60

type Board = { court: number | null; now: string; current: Match | null; waiting: string | null; matches: Match[] }

/** "4:05" under an hour, else "2h 15m". */
export function untilStart(seconds: number): string {
  if (seconds < 3600) return clock(seconds)
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

type Send = (action: Action, body?: Record<string, unknown>) => void

function Timer({ startedAt }: { startedAt: number }) {
  const now = useNow()
  const left = GAME_SECONDS - (now - startedAt) / 1000
  const share = Math.max(0, left / GAME_SECONDS)
  return (
    <p className={left <= 0 ? 'timer done' : 'timer'} aria-label="Time left" style={{ '--left': share } as CSSProperties}>
      {left > 0 ? clock(left) : 'Time!'}
    </p>
  )
}

type CardProps = {
  match: Match
  send: Send
  /** Why the game can't start yet, apart from its time (a team still on another court). */
  waiting?: string | null
  /** Server clock minus this phone's clock (ms), so the countdown matches the server. */
  offset?: number
  /** Admins may start a game before its time. */
  canStartEarly?: boolean
}

export function ScoreCard({ match, send, waiting = null, offset = 0, canStartEarly = false }: CardProps) {
  const now = useNow() + offset
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
    // games start at their time, never as soon as the court is free
    const wait = Math.ceil((Date.parse(match.scheduled_at) - now) / 1000)
    const early = wait > 0
    const begin = (body?: Record<string, unknown>) => {
      setStartedAt(Date.now())
      send('start', body)
    }
    return (
      <section className="scorecard" aria-label="Current game">
        <h2>
          {match.round} · {time(match.scheduled_at)}
        </h2>
        <p className="versus">
          {names[0]} <span>vs</span> {names[1]}
        </p>
        {waiting ? (
          <p role="status" className="warning">
            <Hourglass size={18} /> {waiting}
          </p>
        ) : (
          early && (
            <p className="countdown-start" role="timer" aria-label="Time until this game starts">
              <Clock3 size={18} /> Starts in <strong>{untilStart(wait)}</strong>
            </p>
          )
        )}
        <button
          type="button"
          className="big"
          style={{ width: '100%' }}
          disabled={Boolean(waiting) || early}
          onClick={() => begin()}
        >
          <Play size={26} />
          {early ? `Start at ${time(match.scheduled_at)}` : 'Start game'}
        </button>
        {canStartEarly && early && !waiting && (
          <button type="button" className="secondary" onClick={() => begin({ early: true })}>
            Start early (admin)
          </button>
        )}
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
              <Plus size={28} />1
            </button>
            <button type="button" className="secondary" aria-label={`Take a point from ${names[side]}`} onClick={() => change(side, -1)} disabled={scores[side] <= 0}>
              <Minus size={18} />1
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
            <Flag size={18} />
            Final: reached 11
          </button>
          <button type="button" className="secondary" onClick={() => (a === b ? setStep('sudden') : finish('clock_lead'))}>
            <TimerIcon size={18} />
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
  const { data, receivedAt, loading, error, reload } = useApi<Board>(token ? path : null, token)
  const queue = useSyncExternalStore(judgeQueue.subscribe, judgeQueue.getState)
  // a refused start (say, a team still on another court) puts the Start button back
  const [refusedStarts, setRefusedStarts] = useState(0)

  useEffect(() => {
    judgeQueue.token = token
    judgeQueue.onSent = (match) => {
      if (match.status === 'completed' || match.status === 'cancelled') reload()
    }
    judgeQueue.onRefused = (item) => {
      if (item.action === 'start') setRefusedStarts((n) => n + 1)
      reload()
    }
    const retry = () => void judgeQueue.flush()
    retry()
    const id = setInterval(retry, 5000)
    window.addEventListener('online', retry)
    return () => {
      clearInterval(id)
      window.removeEventListener('online', retry)
      judgeQueue.onSent = null
      judgeQueue.onRefused = null
    }
  }, [token, reload])

  if (!token) return <Navigate to="/staff" replace />
  if (auth?.mustChange) return <Navigate to="/staff/password" replace />
  const upcoming = data?.matches.filter((m) => m.status === 'scheduled' && m.id !== data.current?.id) ?? []
  return (
    <>
      <header className="judge-head">
        <h1>{court ? `Court ${court}` : 'Judge'}</h1>
        <span className="who">{auth?.name}</span>
        <span className={queue.offline ? 'tag live' : 'tag final'}>
          {queue.offline ? <WifiOff size={14} /> : <Wifi size={14} />}
          {queue.offline ? 'Offline' : 'Online'}
        </span>
        <button type="button" className="link" onClick={signOut}>
          <LogOut size={16} />
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
          key={`${data.current.id}-${refusedStarts}`}
          match={data.current}
          waiting={data.waiting}
          offset={receivedAt ? Date.parse(data.now) - receivedAt : 0}
          canStartEarly={auth?.role === 'admin'}
          send={(action, body) => void judgeQueue.push({ matchId: data.current!.id, action, body })}
        />
      )}
      {upcoming.length > 0 && (
        <section aria-label="Later on this court" className="card">
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
