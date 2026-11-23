import { Clock } from 'lucide-react'
import { useSearchParams } from 'react-router'

import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import YourGame from '../components/YourGame'
import { accent } from '../lib/brand'
import { time } from '../lib/format'
import { useApi } from '../lib/live'
import { useMyTeam } from '../lib/myteam'
import type { Match, TeamBrief } from '../lib/types'

// "team=all" lets a logged-in player see every team (their own team is their default)
const ALL = 'all'

export default function Schedule() {
  const [params, setParams] = useSearchParams()
  const { team: mine, loading: findingMine } = useMyTeam()
  const chosen = params.get('team')
  // a logged-in player starts on their own team's day (owner, 2026-11-22); links with
  // ?team=N still work, and "All teams" shows everyone
  const team = chosen === ALL ? '' : (chosen ?? (mine ? String(mine.number) : ''))
  const query = new URLSearchParams()
  const filters: [string, string | null][] = [['group', params.get('group')], ['court', params.get('court')], ['team', team]]
  for (const [key, value] of filters) {
    if (value) query.set(key, value)
  }
  // wait for a player's team, so they never see everyone's games flash by first
  const { data, loading, error } = useApi<Match[]>(findingMine ? null : `/public/schedule?${query}`)
  // the team list barely changes and CloudFront caches it, so a slow refresh is plenty
  const teams = useApi<TeamBrief[]>('/public/teams', null, 60_000)
  // only drawn teams have a number, and the number is what the schedule filters on
  const picks = (teams.data ?? [])
    .filter((t) => t.number !== null)
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const group = params.get('group') ?? ''
  const mineShown = mine !== null && team === String(mine.number)
  const slots: [string, Match[]][] = []
  for (const match of data ?? []) {
    const at = time(match.scheduled_at)
    if (slots.at(-1)?.[0] === at) slots.at(-1)![1].push(match)
    else slots.push([at, [match]])
  }
  return (
    <>
      <h1>{mineShown ? 'Your schedule' : 'Schedule'}</h1>
      <div className="filters">
        <div className="chips" role="group" aria-label="Group">
          {['', 'A', 'B', 'C', 'D'].map((g) => (
            <button key={g || 'all'} type="button" aria-pressed={group === g} style={accent(g)} onClick={() => set('group', g)}>
              {g ? `Group ${g}` : 'All groups'}
            </button>
          ))}
        </div>
        <label>
          Court
          <select value={params.get('court') ?? ''} onChange={(e) => set('court', e.target.value)}>
            <option value="">All</option>
            {Array.from({ length: 9 }, (_, i) => (
              <option key={i + 1}>{i + 1}</option>
            ))}
          </select>
        </label>
        {picks.length > 0 && (
          <label>
            Team
            <select value={chosen === ALL ? ALL : team} onChange={(e) => set('team', e.target.value)}>
              <option value={mine ? ALL : ''}>All teams</option>
              {picks.map((t) => (
                <option key={t.id} value={t.number!}>
                  #{t.number} {t.name}
                  {t.id === mine?.id ? ' (your team)' : ''}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <Status loading={loading} error={error} />
      {mineShown && data && <YourGame games={data} team={mine} />}
      {data && data.length === 0 && <p className="info">No games yet. The schedule is published after the draw.</p>}
      {mineShown && slots.length > 0 && <h2 className="day-head">Your whole day</h2>}
      {slots.map(([at, matches]) => (
        <section key={at} aria-label={at}>
          <h2 className="time-head">
            <Clock size={16} />
            {at}
          </h2>
          <div className="matches">
            {matches.map((m) => (
              <MatchCard key={m.id} match={m} highlight={mine?.id} />
            ))}
          </div>
        </section>
      ))}
    </>
  )
}
