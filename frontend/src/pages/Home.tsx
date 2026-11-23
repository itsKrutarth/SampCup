import { ChevronRight, Flame, GitBranch, LayoutGrid, ListOrdered, LogIn, MapPin, Navigation, Phone, Trophy, UserPlus, Users } from 'lucide-react'
import { Link } from 'react-router'

import CourtBoard from '../components/CourtBoard'
import Countdown from '../components/Countdown'
import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import TeamAvatar from '../components/TeamAvatar'
import Ticker from '../components/Ticker'
import YourGame from '../components/YourGame'
import { DAY_PLAN, TAGLINE } from '../lib/brand'
import { useAuth } from '../lib/auth'
import { monthDay, weekday } from '../lib/format'
import { accent } from '../lib/brand'
import { useApi } from '../lib/live'
import { useMyTeam } from '../lib/myteam'
import type { GroupTable, Match, Overview, TeamBrief } from '../lib/types'

const PHASE = {
  registration: 'Registration is open',
  scheduled: 'Schedule is out',
  group_play: 'Group play under way',
  knockout: 'Knockout rounds under way',
  finished: 'Tournament complete',
}

const FORMAT = [
  [Users, 'Pair up', 'Two players from the same center form a doubles team.'],
  [LayoutGrid, 'Group play', 'Four random groups. Every team plays at least 8 games, never more than 2 in a row.'],
  [GitBranch, 'Knockout', 'The top 4 of each group make the Round of 16, then quarterfinals and semifinals.'],
  [Trophy, 'The Final', 'Best of 3 on court 1. First to 11, no win-by-2, 12-minute clock.'],
] as const

const GLANCE = [
  ['9', 'Courts'],
  ['4', 'Groups'],
  ['8+', 'Games each'],
  ['16', 'Knockout spots'],
  ['3', 'Game final'],
] as const

function Leaderboard() {
  const { data } = useApi<{ groups: Record<string, GroupTable> }>('/public/standings')
  const groups = Object.entries(data?.groups ?? {})
  if (!groups.length) return null
  return (
    <section aria-label="Leaderboard">
      <div className="section-head">
        <h2>
          <Trophy size={22} /> Leaderboard
        </h2>
        <Link to="/standings">Full standings</Link>
      </div>
      <div className="leaderboard">
        {groups.map(([letter, table]) => (
          <div key={letter} className="lb-group" style={accent(letter)}>
            <h3>Group {letter}</h3>
            <ol>
              {table.rows.slice(0, 4).map((row) => (
                <li key={row.team_id}>
                  <span className={`rank rank-${row.rank}`}>{row.rank}</span>
                  <TeamAvatar team={{ id: row.team_id, name: row.team_name, number: row.team_number, group: letter }} />
                  <span className="name">{row.team_name}</span>
                  <span className="record">
                    {row.wins}-{row.losses}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  )
}

export function ChampionCard({ name }: { name: string }) {
  return (
    <div className="champion-card" role="status">
      <Trophy size={44} />
      <div>
        <p className="label">Champions</p>
        <p className="name">{name}</p>
      </div>
    </div>
  )
}

/** What the hero offers depends on who is looking: visitor, player (with or without a team) or staff. */
function AccountActions({ registrationOpen }: { registrationOpen: boolean }) {
  const { auth } = useAuth()
  const player = auth?.kind === 'player'
  // only picks which buttons to show, so a slow refresh is plenty (and spares the server)
  const me = useApi<{ team: unknown }>(player ? '/player/me' : null, auth?.token, 60_000)
  if (auth?.kind === 'staff') return null
  if (player) {
    if (!me.data) return null
    return (
      <Link className="button" to="/my-team">
        <Users size={18} />
        {me.data.team ? 'My team' : 'Pick your partner'}
      </Link>
    )
  }
  return (
    <>
      {registrationOpen && (
        <Link className="button" to="/join">
          <UserPlus size={18} />
          Create your account
        </Link>
      )}
      <Link className="button secondary" to="/login">
        <LogIn size={18} />
        Log in
      </Link>
    </>
  )
}

/** The logged-in player's next game (or the one they are playing), from the cached public schedule. */
function HomeYourGame({ team }: { team: TeamBrief }) {
  const { data } = useApi<Match[]>(`/public/schedule?team=${team.number}`, null, 10_000)
  return data ? <YourGame games={data} team={team} link /> : null
}

export default function Home() {
  const { auth } = useAuth()
  const { team: myTeam } = useMyTeam()
  const { data, loading, error } = useApi<Overview>('/public/overview')
  if (!data) return <Status loading={loading} error={error} />
  const { tournament } = data
  const live = data.phase === 'group_play' || data.phase === 'knockout'
  // Once the first game starts the page is about play (owner, 2026-11-22): the hero stops at
  // the tagline, play comes first, and the venue moves below the leaderboard.
  const started = live || data.phase === 'finished'
  // "SAMP Cup 2026": the year gets the lime highlight
  const [, name, year] = tournament.name.match(/^(.*?)(\d{4})?$/) ?? ['', tournament.name, '']
  const venue = tournament.venue_name && (
    <address className="venue">
      <strong>{tournament.venue_name}</strong>
      <span>{tournament.venue_address}</span>
      {tournament.venue_address && (
        <a
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${tournament.venue_name}, ${tournament.venue_address}`)}`}
          target="_blank"
          rel="noreferrer"
        >
          <Navigation size={16} />
          Directions
        </a>
      )}
    </address>
  )
  const glance = (
    <ul className="glance" aria-label="At a glance">
      {GLANCE.map(([value, label]) => (
        <li key={label}>
          <strong>{value}</strong>
          <span>{label}</span>
        </li>
      ))}
    </ul>
  )
  return (
    <>
      {data.live.length > 0 && <Ticker matches={data.live} />}
      <section className="hero">
        <img className="murti" src="/brand/swaminarayan.webp" width={497} height={332} alt="Bhagwan Swaminarayan" />
        <div className="hero-top">
          {/* the official logo (owner, 2026-11-22) in place of the drawn crest */}
          <img className="hero-logo" src="/brand/samp-cup-logo.webp" width={532} height={642} alt="" />
          <h1 className="wordmark">
            {name}
            {year && <span className="year">{year}</span>}
          </h1>
          {tournament.subtitle && <p className="ribbon">{tournament.subtitle}</p>}
          <p className="event-kind">Pickleball Tournament</p>
          <p className="tagline">{TAGLINE}</p>
        </div>
        {!started && (
          <>
            <p className="event-date">{tournament.event_date ? monthDay(tournament.event_date) : 'Date to be announced'}</p>
            <p className="age">
              {tournament.event_date && weekday(tournament.event_date)}
              {tournament.event_date && tournament.age_group && ' · '}
              {tournament.age_group && `Age ${tournament.age_group}`}
            </p>
            {venue}
            <div className="hero-meta">
              <span className="glass">
                <Flame size={16} />
                {PHASE[data.phase]}
              </span>
            </div>
            {tournament.event_date && <Countdown eventDate={tournament.event_date} />}
            <div className="cta-row">
              {data.phase === 'registration' ? (
                <AccountActions registrationOpen={tournament.registration_open} />
              ) : (
                <Link className="button" to="/schedule">
                  Full schedule
                  <ChevronRight size={18} />
                </Link>
              )}
              <Link className="button secondary" to="/standings">
                <ListOrdered size={18} />
                Standings
              </Link>
            </div>
            {data.phase === 'registration' && !auth && (
              <p className="tagline">Registered on the MySatsang app? Create your account, then invite your partner.</p>
            )}
          </>
        )}
      </section>

      {data.champion && <ChampionCard name={data.champion.name} />}
      {myTeam && data.phase !== 'registration' && <HomeYourGame team={myTeam} />}
      {!started && glance}

      {data.phase !== 'registration' && data.phase !== 'finished' && (
        <section aria-label="Courts">
          <div className="section-head">
            <h2>
              {data.live.length > 0 && <span className="live-dot" />} Courts
            </h2>
            <Link to="/schedule">Order of play</Link>
          </div>
          <CourtBoard courts={data.courts} />
        </section>
      )}
      {data.upcoming.length > 0 && (
        <section aria-label="Up next">
          <div className="section-head">
            <h2>Up next</h2>
            <Link to="/schedule">All games</Link>
          </div>
          <div className="matches">
            {data.upcoming.map((m) => (
              <MatchCard key={m.id} match={m} highlight={myTeam?.id} />
            ))}
          </div>
        </section>
      )}

      {data.phase !== 'registration' && <Leaderboard />}

      {started && venue && (
        <section aria-label="Venue" className="card venue-card">
          {venue}
        </section>
      )}
      {started && glance}

      <div className="two-col">
        <section aria-label="How it works">
          <h2>How SAMP Cup works</h2>
          <ol className="steps">
            {FORMAT.map(([Icon, title, text]) => (
              <li key={title}>
                <Icon size={26} />
                <h3>{title}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </section>
        <section aria-label="The day">
          <h2>
            <MapPin size={22} /> The day
          </h2>
          <ol className="timeline">
            {DAY_PLAN.map(([at, what]) => (
              <li key={at}>
                <time>{at}</time>
                {what}
              </li>
            ))}
          </ol>
          {tournament.contacts && (
            <div className="card" aria-label="Questions">
              <h3>
                <Phone size={18} /> Questions?
              </h3>
              <p className="contacts">{tournament.contacts}</p>
            </div>
          )}
        </section>
      </div>
    </>
  )
}
