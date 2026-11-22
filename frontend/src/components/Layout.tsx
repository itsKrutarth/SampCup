import { CalendarClock, GitBranch, Gavel, House, ListOrdered, Megaphone, ShieldCheck, UserPlus, UserRound } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../lib/auth'
import { TAGLINE } from '../lib/brand'
import { MockClockContext } from '../lib/clock'
import { useApi } from '../lib/live'
import type { Announcement, Overview } from '../lib/types'
import Logo from './Logo'
import VenueClock from './VenueClock'

export function Banner({ announcements }: { announcements?: Announcement[] }) {
  if (!announcements?.length) return null
  return (
    <section className="banner" aria-label="Announcements">
      {announcements.map((a) => (
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

export function BapsArt() {
  return (
    <img
      className="footer-art"
      src="/brand/baps-footer.webp"
      width={1425}
      height={300}
      loading="lazy"
      alt="Brahmaswarup Pramukh Swami Maharaj, the BAPS emblem and Pragat Brahmaswarup Mahant Swami Maharaj. BAPS Swaminarayan Sanstha"
    />
  )
}

function Footer() {
  const { auth } = useAuth()
  return (
    <footer className="footer">
      <nav className="footer-links" aria-label="Footer">
        <NavLink to="/schedule">Order of play</NavLink>
        <NavLink to="/standings">Group standings</NavLink>
        <NavLink to="/bracket">Knockout bracket</NavLink>
        {auth?.kind === 'player' ? <NavLink to="/my-team">My account</NavLink> : <NavLink to="/login">Player login</NavLink>}
        <NavLink to="/staff">Staff area</NavLink>
      </nav>
      <BapsArt />
      <p>SAMP Cup 2026 · {TAGLINE}</p>
    </footer>
  )
}

export default function Layout() {
  const { auth } = useAuth()
  const { data } = useApi<Overview>('/public/overview')
  const account =
    auth?.kind === 'player'
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
    <MockClockContext.Provider value={data?.tournament.mock_clock ?? null}>
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
        <VenueClock />
      </header>
      <Banner announcements={data?.announcements} />
      <main className="page">
        <Outlet />
      </main>
      <Footer />
    </MockClockContext.Provider>
  )
}
