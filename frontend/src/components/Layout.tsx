import { CalendarClock, GitBranch, Gavel, House, ListOrdered, Megaphone, ShieldCheck, UserPlus, UserRound } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../lib/auth'
import { TAGLINE } from '../lib/brand'
import { useApi } from '../lib/live'
import type { Overview } from '../lib/types'
import Logo from './Logo'

export function Banner() {
  const { data } = useApi<Overview>('/public/overview')
  if (!data?.announcements.length) return null
  return (
    <section className="banner" aria-label="Announcements">
      {data.announcements.map((a) => (
        <div key={a.id} className="banner-item">
          <Megaphone size={20} />
          <p>
            <strong>{a.title}</strong>
            {a.body ? ` ${a.body}` : ''}
          </p>
        </div>
      ))}
    </section>
  )
}

export default function Layout() {
  const { auth } = useAuth()
  const account =
    auth?.kind === 'team'
      ? { to: '/my-team', label: 'My team', Icon: UserRound }
      : auth?.kind === 'staff'
        ? auth.role === 'admin'
          ? { to: '/admin', label: 'Admin', Icon: ShieldCheck }
          : { to: '/judge', label: 'Judge', Icon: Gavel }
        : { to: '/join', label: 'Join', Icon: UserPlus }
  const links = [
    { to: '/', label: 'Home', Icon: House },
    { to: '/schedule', label: 'Schedule', Icon: CalendarClock },
    { to: '/standings', label: 'Standings', Icon: ListOrdered },
    { to: '/bracket', label: 'Bracket', Icon: GitBranch },
    account,
  ]
  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">
          <Logo size={38} />
          <span>
            SAMP Cup
            <small>2026 · New England</small>
          </span>
        </NavLink>
        <nav className="nav" aria-label="Main">
          {links.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}>
              <Icon size={20} />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Banner />
      <main className="page">
        <Outlet />
      </main>
      <footer className="footer">SAMP Cup 2026 · {TAGLINE}</footer>
    </>
  )
}
