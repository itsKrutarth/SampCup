import { Link } from 'react-router'

import type { Match, TeamBrief } from '../lib/types'
import MatchCard from './MatchCard'

/**
 * A logged-in player's own game: the one on court now, else their next one. Nothing once
 * their day is over. `games` are their team's games in schedule order.
 */
export default function YourGame({ games, team, link = false }: { games: Match[]; team: TeamBrief; link?: boolean }) {
  const now = games.find((m) => m.status === 'in_progress')
  const game = now ?? games.find((m) => m.status === 'scheduled')
  if (!game) return null
  return (
    <section aria-label="Your game" className="your-game">
      <div className="section-head">
        <h2>
          {now && <span className="live-dot" />} {now ? 'Your game now' : 'Your next game'}
        </h2>
        {link && <Link to="/schedule">Your whole day</Link>}
      </div>
      <MatchCard match={game} highlight={team.id} />
    </section>
  )
}
