import { Hash, MapPin, Medal, Timer, Users, Utensils } from 'lucide-react'
import type { ReactNode } from 'react'
import { useParams } from 'react-router'

import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import TeamAvatar from '../components/TeamAvatar'
import { accent } from '../lib/brand'
import { clock, time } from '../lib/format'
import { useApi } from '../lib/live'
import type { TeamPage as Team } from '../lib/types'

const ORDINAL = ['', '1st', '2nd', '3rd']

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="fact">
      <dt>
        {icon}
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  )
}

export function TeamDetails({ team }: { team: Team }) {
  const s = team.standing
  return (
    <>
      <section className="team-hero" style={accent(team.group)}>
        <TeamAvatar team={team} large />
        <div>
          <h1>{team.name}</h1>
          <p>
            {team.number ? `Team #${team.number}` : 'Number drawn at check-in'}
            {team.group ? ` · Group ${team.group}` : ''}
          </p>
        </div>
      </section>
      {team.status !== 'active' && (
        <p className="warning" role="status">
          {team.status === 'waitlist' ? 'On the waitlist' : 'Withdrawn'}
        </p>
      )}
      <dl className="facts">
        <Fact icon={<MapPin size={14} />} label="Center">
          {team.center}
        </Fact>
        {team.players && (
          <Fact icon={<Users size={14} />} label="Players">
            {team.players.map((p) => p.name).join(' & ')}
          </Fact>
        )}
        {team.group && (
          <Fact icon={<Hash size={14} />} label="Group">
            {team.group}
          </Fact>
        )}
        {team.lunch_start && (
          <Fact icon={<Utensils size={14} />} label="Lunch">
            {time(team.lunch_start)}, 51 min
          </Fact>
        )}
        {s && (
          <Fact icon={<Medal size={14} />} label="Group rank">
            {ORDINAL[s.rank] ?? `${s.rank}th`} · {s.wins}-{s.losses}
          </Fact>
        )}
        {s && (
          <Fact icon={<Timer size={14} />} label="Average game">
            {clock(s.avg_seconds)}
          </Fact>
        )}
      </dl>
      {team.next_match && (
        <section aria-label="Next game">
          <h2>Next game</h2>
          <MatchCard match={team.next_match} highlight={team.id} />
        </section>
      )}
      <h2>All games</h2>
      {team.matches.length === 0 && <p className="info">Your games appear here after the draw.</p>}
      <div className="matches">
        {team.matches.map((m) => (
          <MatchCard key={m.id} match={m} highlight={team.id} />
        ))}
      </div>
    </>
  )
}

export default function TeamPage() {
  const { number } = useParams()
  const { data, loading, error } = useApi<Team>(`/public/teams/${number}`)
  if (!data) return <Status loading={loading} error={error} />
  return <TeamDetails team={data} />
}
