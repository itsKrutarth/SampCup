import { time } from '../lib/format'
import type { Match, TeamBrief } from '../lib/types'

const STATUS = { scheduled: '', in_progress: 'Live', completed: 'Final', cancelled: 'Not needed' }

export function teamLabel(team: TeamBrief | null, source: string | null): string {
  if (team) return team.number ? `#${team.number} ${team.name}` : team.name
  return source ?? 'To be decided'
}

export default function MatchCard({ match, highlight }: { match: Match; highlight?: number }) {
  const scored = match.score_a !== null && match.score_b !== null
  const side = (team: TeamBrief | null, source: string | null, score: number | null) => (
    <div
      className={[
        'side',
        match.winner_id && team?.id === match.winner_id ? 'winner' : '',
        highlight && team?.id === highlight ? 'mine' : '',
      ].join(' ')}
    >
      <span>{teamLabel(team, source)}</span>
      {scored && <span className="score">{score}</span>}
    </div>
  )
  return (
    <article className={`match match-${match.status}`} aria-label={`${match.code} ${match.round}`}>
      <header>
        <span>{time(match.scheduled_at)}</span>
        <span>Court {match.court}</span>
        <span>{match.phase === 'group' ? `Group ${match.group}` : match.round}</span>
        {STATUS[match.status] && <span className="tag">{STATUS[match.status]}</span>}
      </header>
      {side(match.team_a, match.source_a, match.score_a)}
      {side(match.team_b, match.source_b, match.score_b)}
    </article>
  )
}
