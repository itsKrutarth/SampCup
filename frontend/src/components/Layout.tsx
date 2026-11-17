import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../lib/auth'
import { useApi } from '../lib/live'
import type { Overview } from '../lib/types'

export function Banner() {
  const { data } = useApi<Overview>('/public/overview')
  if (!data?.announcements.length) return null
  return (
    <section className="banner" aria-label="Announcements">
      {data.announcements.map((a) => (
        <p key={a.id}>
          <strong>{a.title}</strong>
          {a.body ? ` ${a.body}` : ''}
        </p>
      ))}
    </section>
  )
}

export default function Layout() {
  const { auth } = useAuth()
  const account =
    auth?.kind === 'team'
      ? { to: '/my-team', label: 'My team' }
      : auth?.kind === 'staff'
        ? { to: auth.role === 'admin' ? '/admin' : '/judge', label: auth.role === 'admin' ? 'Admin' : 'Judge' }
        : { to: '/join', label: 'Join' }
  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">
          SAMP Cup
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/schedule">Schedule</NavLink>
          <NavLink to="/standings">Standings</NavLink>
          <NavLink to="/bracket">Bracket</NavLink>
          <NavLink to={account.to}>{account.label}</NavLink>
        </nav>
      </header>
      <Banner />
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
