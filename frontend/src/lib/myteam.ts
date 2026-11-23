import { useAuth } from './auth'
import { useApi } from './live'
import type { TeamBrief } from './types'

/**
 * The logged-in player's team once it has been drawn (it has a number, which the schedule
 * filters on); null for visitors, staff and players without a drawn team. `loading` is true
 * while a player's team is still being looked up, so pages can wait instead of flashing
 * everyone's games first.
 */
export function useMyTeam(): { team: TeamBrief | null; loading: boolean } {
  const { auth } = useAuth()
  const token = auth?.kind === 'player' ? auth.token : null
  // a team changes rarely: a slow refresh is plenty and spares the server
  const me = useApi<{ team: TeamBrief | null }>(token ? '/player/me' : null, token, 60_000)
  const team = me.data?.team && me.data.team.number !== null ? me.data.team : null
  return { team, loading: Boolean(token) && !me.data && !me.error }
}
