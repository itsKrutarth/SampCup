import { Navigate, NavLink, Route, Routes } from 'react-router'

import { useAuth } from '../../lib/auth'
import Announcements from './Announcements'
import Audit from './Audit'
import Overview from './Overview'
import Players from './Players'
import Results from './Results'
import ScheduleAdmin from './ScheduleAdmin'
import Staff from './Staff'
import Teams from './Teams'

const TABS = [
  ['', 'Overview'],
  ['players', 'Players'],
  ['teams', 'Teams'],
  ['schedule', 'Draw & schedule'],
  ['results', 'Results'],
  ['announcements', 'Announcements'],
  ['staff', 'Judges & admins'],
  ['audit', 'Audit log'],
] as const

export default function Admin() {
  const { auth, signOut } = useAuth()
  if (auth?.kind !== 'staff') return <Navigate to="/staff" replace />
  if (auth.role !== 'admin') return <Navigate to="/judge" replace />
  return (
    <div className="admin">
      <header className="judge-head">
        <h1>Admin</h1>
        <span>{auth.name}</span>
        <button type="button" className="link" onClick={signOut}>
          Log out
        </button>
      </header>
      <nav className="tabs" aria-label="Admin">
        {TABS.map(([path, label]) => (
          <NavLink key={path} to={`/admin${path ? `/${path}` : ''}`} end>
            {label}
          </NavLink>
        ))}
      </nav>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="players" element={<Players />} />
        <Route path="teams" element={<Teams />} />
        <Route path="schedule" element={<ScheduleAdmin />} />
        <Route path="results" element={<Results />} />
        <Route path="announcements" element={<Announcements />} />
        <Route path="staff" element={<Staff />} />
        <Route path="audit" element={<Audit />} />
      </Routes>
    </div>
  )
}
