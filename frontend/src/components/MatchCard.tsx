import { Check, Clock, MapPin } from 'lucide-react'

import { accent } from '../lib/brand'
import { time } from '../lib/format'
import type { Match, TeamBrief } from '../lib/types'
import TeamAvatar from './TeamAvatar'

const STATUS = { scheduled: '', in_progress: 'Live', completed: 'Final', cancelled: 'Not needed' }

export function teamLabel(team: TeamBrief | null, source: string | null): string {
  if (team) return team.number ? `#${team.number} ${team.name}` : team.name
  return source ?? 'To be decided'
}

export default function MatchCard({ match, highlight }: { match: Match; highlight?: number }) {
  const scored = match.score_a !== null && match.score_b !== null
  const side = (team: TeamBrief | null, source: string | null, score: number | null) => {
    const won = Boolean(match.winner_id && team?.id === match.winner_id)
    return (
      <div className={['side', won ? 'winner' : '', highlight && team?.id === highlight ? 'mine' : ''].join(' ')}>
        {team ? <TeamAvatar team={team} /> : <span className="avatar">?</span>}
        <span className={team ? 'name' : 'name tbd'}>{team ? team.name : (source ?? 'To be decided')}</span>
        {won && <Check size={16} aria-label="Winner" />}
        {scored && <span className="score">{score}</span>}
      </div>
    )
  }
  const status = STATUS[match.status]
  return (
    <article
      className={`match match-${match.status}`}
      style={accent(match.group, match.phase === 'knockout')}
      aria-label={`${match.code} ${match.round}`}
    >
      <header>
        <span className="pill">
          <Clock size={13} />
          {time(match.scheduled_at)}
        </span>
        <span className="pill">
          <MapPin size={13} />
          Court {match.court}
        </span>
        <span className="pill group">{match.phase === 'group' ? `Group ${match.group}` : match.round}</span>
        {status && (
          <span className={`tag ${match.status === 'in_progress' ? 'live' : match.status === 'completed' ? 'final' : ''}`}>
            {match.status === 'in_progress' && <span className="live-dot" />}
            {status}
          </span>
        )}
      </header>
      {side(match.team_a, match.source_a, match.score_a)}
      {side(match.team_b, match.source_b, match.score_b)}
    </article>
  )
}
