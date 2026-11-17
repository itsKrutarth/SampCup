import { Link } from 'react-router'

import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { dateLong } from '../lib/format'
import { useApi } from '../lib/live'
import type { Overview } from '../lib/types'

const PHASE = {
  registration: 'Registration is open',
  scheduled: 'Schedule is out',
  group_play: 'Group play under way',
  knockout: 'Knockout rounds under way',
  finished: 'Tournament complete',
}

export default function Home() {
  const { data, loading, error } = useApi<Overview>('/public/overview')
  if (!data) return <Status loading={loading} error={error} />
  const { tournament } = data
  return (
    <>
      <section className="hero">
        <h1>{tournament.name}</h1>
        <p>{dateLong(tournament.event_date)}</p>
        <p className="badge">{PHASE[data.phase]}</p>
        {data.champion && (
          <p className="champion">
            Champions: <strong>{data.champion.name}</strong>
          </p>
        )}
      </section>
      {data.phase === 'registration' && (
        <section className="actions">
          <p>
            {data.teams} of {tournament.team_cap} teams formed
            {data.waitlist ? `, ${data.waitlist} on the waitlist` : ''}.
          </p>
          {tournament.registration_open && (
            <Link className="button" to="/join">
              Join with your partner
            </Link>
          )}
          <Link to="/login">Team login</Link>
        </section>
      )}
      {data.live.length > 0 && (
        <section aria-label="Playing now">
          <h2>Playing now</h2>
          <div className="matches">
            {data.live.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}
      {data.upcoming.length > 0 && (
        <section aria-label="Up next">
          <h2>Up next</h2>
          <div className="matches">
            {data.upcoming.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
