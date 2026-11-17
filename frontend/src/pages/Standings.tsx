import StandingsTables from '../components/Standings'
import Status from '../components/Status'
import { useApi } from '../lib/live'
import type { GroupTable } from '../lib/types'

export default function Standings() {
  const { data, loading, error } = useApi<{ groups: Record<string, GroupTable> }>('/public/standings')
  return (
    <>
      <h1>Standings</h1>
      <p className="hint">Top 4 of each group go to the Round of 16.</p>
      <Status loading={loading} error={error} />
      {data && <StandingsTables groups={data.groups} />}
    </>
  )
}
