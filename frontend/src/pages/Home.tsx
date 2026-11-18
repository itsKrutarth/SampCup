import { ChevronRight, Flame, GitBranch, LayoutGrid, ListOrdered, LogIn, MapPin, Navigation, Phone, Radio, Trophy, UserPlus, Users } from 'lucide-react'
import { Link } from 'react-router'

import Countdown from '../components/Countdown'
import Logo from '../components/Logo'
import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { DAY_PLAN, TAGLINE } from '../lib/brand'
import { monthDay, weekday } from '../lib/format'
import { useApi } from '../lib/live'
import type { Overview } from '../lib/types'

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

export default function Home() {
  const { data, loading, error } = useApi<Overview>('/public/overview')
  if (!data) return <Status loading={loading} error={error} />
  const { tournament } = data
  const live = data.phase === 'group_play' || data.phase === 'knockout'
  // "SAMP Cup 2026": the year gets the lime highlight
  const [, name, year] = tournament.name.match(/^(.*?)(\d{4})?$/) ?? ['', tournament.name, '']
  return (
    <>
      <section className="hero">
        <div className="hero-top">
          <Logo size={96} />
          <h1 className="wordmark">
            {name}
            {year && <span className="year">{year}</span>}
          </h1>
          {tournament.subtitle && <p className="ribbon">{tournament.subtitle}</p>}
          <p className="event-kind">Pickleball Tournament</p>
          <p className="tagline">{TAGLINE}</p>
        </div>
        <p className="event-date">{tournament.event_date ? monthDay(tournament.event_date) : 'Date to be announced'}</p>
        <p className="age">
          {tournament.event_date && weekday(tournament.event_date)}
          {tournament.event_date && tournament.age_group && ' · '}
          {tournament.age_group && `Age ${tournament.age_group}`}
        </p>
        {tournament.venue_name && (
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
        )}
        <div className="hero-meta">
          <span className={live ? 'glass live' : 'glass'}>
            {live ? <Radio size={16} /> : <Flame size={16} />}
            {PHASE[data.phase]}
          </span>
        </div>
        {tournament.event_date && data.phase !== 'finished' && <Countdown eventDate={tournament.event_date} />}
        <div className="cta-row">
          {data.phase === 'registration' && tournament.registration_open && (
            <Link className="button" to="/join">
              <UserPlus size={18} />
              Join with your partner
            </Link>
          )}
          {data.phase === 'registration' ? (
            <Link className="button secondary" to="/login">
              <LogIn size={18} />
              Team login
            </Link>
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
        {data.phase === 'registration' && (
          <p className="tagline">Registered on the MySatsang app? Pair up with your partner here.</p>
        )}
      </section>

      {data.champion && <ChampionCard name={data.champion.name} />}

      <ul className="stats" aria-label="Tournament numbers">
        <li className="stat">
          <span className="stat-icon">
            <Users size={20} />
          </span>
          <div>
            <strong>
              {data.teams}/{tournament.team_cap}
            </strong>
            <span>teams formed</span>
          </div>
        </li>
        {data.waitlist > 0 && (
          <li className="stat">
            <span className="stat-icon">
              <UserPlus size={20} />
            </span>
            <div>
              <strong>{data.waitlist}</strong>
              <span>on the waitlist</span>
            </div>
          </li>
        )}
        <li className="stat">
          <span className="stat-icon">
            <LayoutGrid size={20} />
          </span>
          <div>
            <strong>9</strong>
            <span>courts</span>
          </div>
        </li>
        <li className="stat">
          <span className="stat-icon">
            <Trophy size={20} />
          </span>
          <div>
            <strong>8+</strong>
            <span>games per team</span>
          </div>
        </li>
      </ul>

      {data.live.length > 0 && (
        <section aria-label="Playing now">
          <div className="section-head">
            <h2>
              <span className="live-dot" /> Playing now
            </h2>
            <Link to="/schedule">Schedule</Link>
          </div>
          <div className="matches">
            {data.live.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
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
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}

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
