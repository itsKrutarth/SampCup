import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { useApi } from '../lib/live'
import type { Match, TeamBrief } from '../lib/types'
import { ChampionCard } from './Home'

const ROUNDS = [
  ['R16', 'Round of 16'],
  ['QF', 'Quarterfinals'],
  ['SF', 'Semifinals'],
  ['F', 'Final (best of 3)'],
] as const

/** "Net Ninjas leads 1-0" once a Final game is done; nothing before. */
function series(games: Match[]): string | null {
  const [a, b] = [games[0]?.team_a, games[0]?.team_b]
  if (!a || !b) return null
  const wins = (id: number) => games.filter((m) => m.status === 'completed' && m.winner_id === id).length
  const [winsA, winsB] = [wins(a.id), wins(b.id)]
  if (winsA + winsB === 0) return null
  if (winsA === winsB) return `Series tied ${winsA}-${winsB}`
  const [leader, high, low] = winsA > winsB ? [a, winsA, winsB] : [b, winsB, winsA]
  return `${leader.name} ${high >= 2 ? 'wins' : 'leads'} ${high}-${low}`
}

export default function Bracket() {
  const { data, loading, error } = useApi<{ matches: Match[]; champion: TeamBrief | null }>('/public/bracket')
  return (
    <>
      <h1>Knockout bracket</h1>
      <Status loading={loading} error={error} />
      {data?.champion && <ChampionCard name={data.champion.name} />}
      {data && data.matches.length === 0 && <p className="info">The bracket fills in after group play.</p>}
      {data && data.matches.length > 0 && (
        <div className="bracket">
          {ROUNDS.map(([prefix, title]) => {
            const games = data.matches.filter((m) => m.code.split('-')[0] === prefix)
            const score = prefix === 'F' ? series(games) : null
            return (
              <section key={prefix} aria-label={title} className={prefix === 'F' ? 'final' : undefined}>
                <h2>{title}</h2>
                {score && <p className="series">{score}</p>}
                {games.map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </section>
            )
          })}
        </div>
      )}
    </>
  )
}
