import { CalendarClock, ClipboardList, Gauge, History, LogOut, Megaphone, ShieldCheck, Trophy, Users, UsersRound } from 'lucide-react'
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
  ['', 'Overview', Gauge],
  ['players', 'Players', Users],
  ['teams', 'Teams', UsersRound],
  ['schedule', 'Draw & schedule', CalendarClock],
  ['results', 'Results', Trophy],
  ['announcements', 'Announcements', Megaphone],
  ['staff', 'Judges & admins', ShieldCheck],
  ['audit', 'Audit log', History],
] as const

export default function Admin() {
  const { auth, signOut } = useAuth()
  if (auth?.kind !== 'staff') return <Navigate to="/staff" replace />
  if (auth.mustChange) return <Navigate to="/staff/password" replace />
  if (auth.role !== 'admin') return <Navigate to="/judge" replace />
  return (
    <div className="admin">
      <header className="judge-head">
        <h1>
          <ClipboardList size={26} /> Admin
        </h1>
        <span className="who">{auth.name}</span>
        <button type="button" className="link" onClick={signOut}>
          <LogOut size={16} />
          Log out
        </button>
      </header>
      <nav className="admin-tabs" aria-label="Admin">
        {TABS.map(([path, label, Icon]) => (
          <NavLink key={path} to={`/admin${path ? `/${path}` : ''}`} end>
            <Icon size={16} />
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
