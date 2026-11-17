import { useSearchParams } from 'react-router'

import MatchCard from '../components/MatchCard'
import Status from '../components/Status'
import { useApi } from '../lib/live'
import type { Match } from '../lib/types'

const FILTERS = ['group', 'court', 'team'] as const

export default function Schedule() {
  const [params, setParams] = useSearchParams()
  const query = new URLSearchParams()
  for (const key of FILTERS) {
    const value = params.get(key)
    if (value) query.set(key, value)
  }
  const { data, loading, error } = useApi<Match[]>(`/public/schedule?${query}`)
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  return (
    <>
      <h1>Schedule</h1>
      <form className="filters" onSubmit={(e) => e.preventDefault()}>
        <label>
          Group
          <select value={params.get('group') ?? ''} onChange={(e) => set('group', e.target.value)}>
            <option value="">All</option>
            {['A', 'B', 'C', 'D'].map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        <label>
          Court
          <select value={params.get('court') ?? ''} onChange={(e) => set('court', e.target.value)}>
            <option value="">All</option>
            {Array.from({ length: 9 }, (_, i) => (
              <option key={i + 1}>{i + 1}</option>
            ))}
          </select>
        </label>
        <label>
          Team #
          <input
            inputMode="numeric"
            value={params.get('team') ?? ''}
            onChange={(e) => set('team', e.target.value.replace(/\D/g, ''))}
          />
        </label>
      </form>
      <Status loading={loading} error={error} />
      {data && data.length === 0 && <p>No games yet. The schedule is published after the draw.</p>}
      <div className="matches">
        {data?.map((m) => (
          <MatchCard key={m.id} match={m} />
        ))}
      </div>
    </>
  )
}
