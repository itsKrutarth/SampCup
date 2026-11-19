import type { CourtGame } from '../lib/types'
import TeamAvatar from './TeamAvatar'

const COURTS = Array.from({ length: 9 }, (_, i) => i + 1)

/** One tile per court: the game on it now, else that court's next one, else free. */
export default function CourtBoard({ courts }: { courts: CourtGame[] }) {
  return (
    <div className="court-board">
      {COURTS.map((court) => {
        const game = courts.find((c) => c.court === court)?.match
        const now = game?.status === 'in_progress'
        return (
          <article key={court} className={now ? 'court-tile on' : 'court-tile'} aria-label={`Court ${court}`}>
            <header>
              <span className="court-no">{court}</span>
              <span className={now ? 'tag live' : 'tag'}>
                {now && <span className="live-dot" />}
                {now ? 'Live' : game ? 'Next' : 'Free'}
              </span>
            </header>
            {game ? (
              [game.team_a, game.team_b].map((team, i) => (
                <div key={i} className="side">
                  {team && <TeamAvatar team={team} />}
                  <span className="name">{team?.name ?? (i ? game.source_b : game.source_a)}</span>
                  {now && <span className="score">{i ? game.score_b : game.score_a}</span>}
                </div>
              ))
            ) : (
              <p className="muted">No game waiting</p>
            )}
          </article>
        )
      })}
    </div>
  )
}
