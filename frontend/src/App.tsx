import { BrowserRouter, Route, Routes } from 'react-router'

import Intro from './components/Intro'
import Layout from './components/Layout'
import { AuthProvider } from './lib/auth'
import Admin from './pages/admin/Admin'
import Bracket from './pages/Bracket'
import Display from './pages/Display'
import Home from './pages/Home'
import Join from './pages/Join'
import Judge from './pages/Judge'
import { ChangePassword, PlayerLogin, StaffLogin } from './pages/Logins'
import PlayerHome from './pages/PlayerHome'
import Schedule from './pages/Schedule'
import Standings from './pages/Standings'
import TeamPage from './pages/TeamPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/display" element={<Display />} />
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="standings" element={<Standings />} />
        <Route path="bracket" element={<Bracket />} />
        <Route path="teams/:number" element={<TeamPage />} />
        <Route path="join" element={<Join />} />
        <Route path="login" element={<PlayerLogin />} />
        <Route path="my-team" element={<PlayerHome />} />
        <Route path="account/password" element={<ChangePassword />} />
        <Route path="staff" element={<StaffLogin />} />
        <Route path="staff/password" element={<ChangePassword />} />
        <Route path="judge" element={<Judge />} />
        <Route path="admin/*" element={<Admin />} />
        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Intro />
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
