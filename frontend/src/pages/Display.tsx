import { Banner } from '../components/Layout'
import MatchCard from '../components/MatchCard'
import StandingsTables from '../components/Standings'
import { useApi } from '../lib/live'
import type { GroupTable, Overview } from '../lib/types'

/** Projector / TV screen: live courts, next games and standings, no controls. */
export default function Display() {
  const { data } = useApi<Overview>('/public/overview')
  const standings = useApi<{ groups: Record<string, GroupTable> }>('/public/standings')
  return (
    <div className="display">
      <h1>{data?.tournament.name ?? 'SAMP Cup'}</h1>
      <Banner />
      {data?.champion && (
        <p className="champion">
          Champions: <strong>{data.champion.name}</strong>
        </p>
      )}
      <section aria-label="Playing now">
        <h2>Playing now</h2>
        <div className="matches">
          {data?.live.map((m) => <MatchCard key={m.id} match={m} />)}
        </div>
      </section>
      <section aria-label="Up next">
        <h2>Up next</h2>
        <div className="matches">
          {data?.upcoming.map((m) => <MatchCard key={m.id} match={m} />)}
        </div>
      </section>
      {standings.data && <StandingsTables groups={standings.data.groups} />}
    </div>
  )
}
