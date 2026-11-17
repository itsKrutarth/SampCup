import { useParams } from 'react-router'

import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { clock, time } from '../lib/format'
import { useApi } from '../lib/live'
import type { TeamPage as Team } from '../lib/types'

export function TeamDetails({ team }: { team: Team }) {
  return (
    <>
      <h1>
        {team.number ? `#${team.number} ` : ''}
        {team.name}
      </h1>
      <dl className="facts">
        {team.group && (
          <>
            <dt>Group</dt>
            <dd>{team.group}</dd>
          </>
        )}
        <dt>Center</dt>
        <dd>{team.center}</dd>
        {team.players && (
          <>
            <dt>Players</dt>
            <dd>{team.players.map((p) => p.name).join(' & ')}</dd>
          </>
        )}
        {team.status !== 'active' && (
          <>
            <dt>Status</dt>
            <dd>{team.status === 'waitlist' ? 'On the waitlist' : 'Withdrawn'}</dd>
          </>
        )}
        {team.lunch_start && (
          <>
            <dt>Lunch</dt>
            <dd>{time(team.lunch_start)} (51 minutes)</dd>
          </>
        )}
        {team.standing && (
          <>
            <dt>Group rank</dt>
            <dd>
              {team.standing.rank} ({team.standing.wins}-{team.standing.losses}, average game{' '}
              {clock(team.standing.avg_seconds)})
            </dd>
          </>
        )}
      </dl>
      {team.next_match && (
        <section aria-label="Next game">
          <h2>Next game</h2>
          <MatchCard match={team.next_match} highlight={team.id} />
        </section>
      )}
      <h2>All games</h2>
      {team.matches.length === 0 && <p>Your games appear here after the draw.</p>}
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
