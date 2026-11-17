import Status from '../../components/Status'
import { useAuth } from '../../lib/auth'
import { time } from '../../lib/format'
import { useApi } from '../../lib/live'

type Entry = {
  id: number
  match: string
  action: string
  old: { score_a?: number | null; score_b?: number | null }
  new: { score_a?: number | null; score_b?: number | null }
  by: string
  reason: string
  at: string
}

const score = (s: Entry['old']) => (s.score_a === null || s.score_a === undefined ? '-' : `${s.score_a}-${s.score_b}`)

export default function Audit() {
  const { auth } = useAuth()
  const { data, loading, error } = useApi<Entry[]>('/admin/audit', auth?.token)
  return (
    <>
      <Status loading={loading} error={error} />
      <table>
        <thead>
          <tr><th>When</th><th>Game</th><th>Change</th><th>By</th><th>Why</th></tr>
        </thead>
        <tbody>
          {data?.map((e) => (
            <tr key={e.id}>
              <td>{time(e.at)}</td>
              <td>{e.match}</td>
              <td>{e.action}: {score(e.old)} → {score(e.new)}</td>
              <td>{e.by}</td>
              <td>{e.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
