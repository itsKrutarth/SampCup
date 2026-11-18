import { accent } from '../lib/brand'
import type { GroupTable } from '../lib/types'
import TeamAvatar from './TeamAvatar'

export default function StandingsTables({ groups, highlight }: { groups: Record<string, GroupTable>; highlight?: number }) {
  const letters = Object.keys(groups)
  if (!letters.length) return <p className="info">Standings appear once the draw is done.</p>
  return (
    <div className="groups">
      {letters.map((letter) => {
        const table = groups[letter]
        return (
          <section key={letter} className="group-card" style={accent(letter)} aria-label={`Group ${letter}`}>
            <header>
              <h2>Group {letter}</h2>
              <small>{table.complete ? 'Complete' : `${table.played} of ${table.total} games played`}</small>
            </header>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Team</th>
                    <th title="Wins">W</th>
                    <th title="Losses">L</th>
                    <th title="Points scored">PF</th>
                    <th title="Points allowed" className="hide-sm">PA</th>
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row) => (
                    <tr
                      key={row.team_id}
                      className={[row.rank <= 4 ? 'qualifies' : '', row.team_id === highlight ? 'mine' : ''].join(' ')}
                    >
                      <td>
                        <span className={`rank rank-${row.rank}`}>{row.rank}</span>
                      </td>
                      <td className="team-cell">
                        <span className="side">
                          <TeamAvatar team={{ id: row.team_id, name: row.team_name, number: row.team_number, group: letter }} />
                          <span className="name">
                            {row.team_name}
                            {row.decided_by && (
                              <>
                                <br />
                                <span className="reason" title="How this place was decided">
                                  {row.decided_by}
                                </span>
                              </>
                            )}
                          </span>
                        </span>
                      </td>
                      <td>{row.wins}</td>
                      <td>{row.losses}</td>
                      <td>{row.points_for}</td>
                      <td className="hide-sm">{row.points_against}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )
      })}
    </div>
  )
}
