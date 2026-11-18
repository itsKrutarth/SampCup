import { accent } from '../lib/brand'
import type { TeamBrief } from '../lib/types'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join('')
}

/** A team's badge: its number in its group color, or its initials before the draw. */
export default function TeamAvatar({ team, large = false }: { team: TeamBrief; large?: boolean }) {
  return (
    <span className={large ? 'avatar lg' : 'avatar'} style={accent(team.group)} aria-hidden="true">
      {team.number ?? initials(team.name)}
    </span>
  )
}
