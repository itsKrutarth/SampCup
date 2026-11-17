import type { GroupTable } from '../lib/types'

export default function StandingsTables({ groups, highlight }: { groups: Record<string, GroupTable>; highlight?: number }) {
  const letters = Object.keys(groups)
  if (!letters.length) return <p>Standings appear once the draw is done.</p>
  return (
    <div className="groups">
      {letters.map((letter) => {
        const table = groups[letter]
        return (
          <section key={letter} aria-label={`Group ${letter}`}>
            <h2>
              Group {letter}{' '}
              <small>
                {table.complete ? 'final' : `${table.played} of ${table.total} games played`}
              </small>
            </h2>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th title="Wins">W</th>
                  <th title="Losses">L</th>
                  <th title="Points scored">PF</th>
                  <th title="Points allowed">PA</th>
                  <th>Placed by</th>
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row) => (
                  <tr
                    key={row.team_id}
                    className={[row.rank <= 4 ? 'qualifies' : '', row.team_id === highlight ? 'mine' : ''].join(' ')}
                  >
                    <td>{row.rank}</td>
                    <td>
                      #{row.team_number} {row.team_name}
                    </td>
                    <td>{row.wins}</td>
                    <td>{row.losses}</td>
                    <td>{row.points_for}</td>
                    <td>{row.points_against}</td>
                    <td>{row.decided_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )
      })}
    </div>
  )
}
