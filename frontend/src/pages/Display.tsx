import { BapsArt, Banner } from '../components/Layout'
import Logo from '../components/Logo'
import MatchCard from '../components/MatchCard'
import StandingsTables from '../components/Standings'
import { TAGLINE } from '../lib/brand'
import { useApi } from '../lib/live'
import type { GroupTable, Overview } from '../lib/types'
import { ChampionCard } from './Home'

/** Projector / TV screen: live courts, next games and standings, no controls. */
export default function Display() {
  const { data } = useApi<Overview>('/public/overview')
  const standings = useApi<{ groups: Record<string, GroupTable> }>('/public/standings')
  return (
    <div className="display">
      <header className="display-head">
        <Logo size={84} />
        <div>
          <h1>{data?.tournament.name ?? 'SAMP Cup'}</h1>
          <p className="muted">{TAGLINE}</p>
        </div>
      </header>
      <Banner announcements={data?.announcements} />
      {data?.champion && <ChampionCard name={data.champion.name} />}
      <section aria-label="Playing now">
        <div className="section-head">
          <h2>
            <span className="live-dot" /> Playing now
          </h2>
        </div>
        <div className="matches">{data?.live.map((m) => <MatchCard key={m.id} match={m} />)}</div>
      </section>
      <section aria-label="Up next">
        <div className="section-head">
          <h2>Up next</h2>
        </div>
        <div className="matches">{data?.upcoming.map((m) => <MatchCard key={m.id} match={m} />)}</div>
      </section>
      {standings.data && (
        <>
          <h2>Standings</h2>
          <StandingsTables groups={standings.data.groups} />
        </>
      )}
      <BapsArt />
    </div>
  )
}
