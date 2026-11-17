import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { useApi } from '../lib/live'
import type { Match, TeamBrief } from '../lib/types'

const ROUNDS = [
  ['R16', 'Round of 16'],
  ['QF', 'Quarterfinals'],
  ['SF', 'Semifinals'],
  ['F', 'Final (best of 3)'],
] as const

export default function Bracket() {
  const { data, loading, error } = useApi<{ matches: Match[]; champion: TeamBrief | null }>('/public/bracket')
  return (
    <>
      <h1>Knockout bracket</h1>
      <Status loading={loading} error={error} />
      {data?.champion && (
        <p className="champion">
          Champions: <strong>{data.champion.name}</strong>
        </p>
      )}
      {data && data.matches.length === 0 && <p>The bracket fills in after group play.</p>}
      <div className="bracket">
        {data &&
          data.matches.length > 0 &&
          ROUNDS.map(([prefix, title]) => (
            <section key={prefix} aria-label={title}>
              <h2>{title}</h2>
              {data.matches
                .filter((m) => m.code.split('-')[0] === prefix)
                .map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
            </section>
          ))}
      </div>
    </>
  )
}
