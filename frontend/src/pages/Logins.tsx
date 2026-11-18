import { KeyRound, LogIn, LogOut, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'

import Logo from '../components/Logo'
import Status from '../components/Status'
import { api, ApiError } from '../lib/api'
import { useAuth, type Auth } from '../lib/auth'
import { useApi } from '../lib/live'
import type { TeamPage } from '../lib/types'
import { TeamDetails } from './TeamPage'

type StaffUser = { username: string; display_name: string; role: 'admin' | 'judge'; court: number | null; must_change_password: boolean }

function useSubmit(handler: (form: FormData) => Promise<void>) {
  const [error, setError] = useState('')
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await handler(new FormData(event.currentTarget))
    } catch (e) {
      setError((e as ApiError).message)
    }
  }
  return { error, onSubmit }
}

function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="auth">
      <header>
        <Logo size={56} />
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
      </header>
      {children}
    </section>
  )
}

function staffAuth(token: string, user: StaffUser): Auth {
  return {
    token,
    kind: 'staff',
    name: user.username,
    role: user.role,
    court: user.court,
    mustChange: user.must_change_password,
  }
}

export function TeamLogin() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const { error, onSubmit } = useSubmit(async (form) => {
    const result = await api<{ token: string; team: { name: string } }>('/auth/team-login', {
      method: 'POST',
      body: { team_name: form.get('team_name'), password: form.get('password') },
    })
    signIn({ token: result.token, kind: 'team', name: result.team.name })
    navigate('/my-team')
  })
  return (
    <AuthCard title="Team login" subtitle="Use your team name and the password your team chose.">
      <form onSubmit={onSubmit} className="stack">
        <label>
          Team name
          <input name="team_name" required autoComplete="username" />
        </label>
        <label>
          Password
          <input name="password" type="password" required autoComplete="current-password" />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}. Judges and admins log in on the staff page.
          </p>
        )}
        <button type="submit">
          <LogIn size={18} />
          Log in
        </button>
        <p className="hint">
          Judge or admin? <Link to="/staff">Staff login</Link>
        </p>
      </form>
    </AuthCard>
  )
}

export function StaffLogin() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const { error, onSubmit } = useSubmit(async (form) => {
    const result = await api<{ token: string; user: StaffUser }>('/auth/staff-login', {
      method: 'POST',
      body: { username: form.get('username'), password: form.get('password') },
    })
    const { user } = result
    signIn(staffAuth(result.token, user))
    navigate(user.must_change_password ? '/staff/password' : user.role === 'admin' ? '/admin' : '/judge')
  })
  return (
    <AuthCard title="Staff login" subtitle="Judges and admins.">
      <form onSubmit={onSubmit} className="stack">
        <label>
          Username
          <input name="username" required autoComplete="username" autoCapitalize="none" />
        </label>
        <label>
          Password or PIN
          <input name="password" type="password" required autoComplete="current-password" />
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit">
          <ShieldCheck size={18} />
          Log in
        </button>
        <p className="hint">
          Playing in the tournament? <Link to="/login">Team login</Link>
        </p>
      </form>
    </AuthCard>
  )
}

/** First login after an admin set the password: the user picks their own. */
export function ChangePassword() {
  const { auth, signIn } = useAuth()
  const navigate = useNavigate()
  const { error, onSubmit } = useSubmit(async (form) => {
    if (form.get('new_password') !== form.get('confirm')) throw new ApiError(400, 'The two new passwords do not match')
    const result = await api<{ user: StaffUser }>('/auth/change-password', {
      method: 'POST',
      token: auth?.token,
      body: { current_password: form.get('current_password'), new_password: form.get('new_password') },
    })
    signIn(staffAuth(auth!.token, result.user))
    navigate(result.user.role === 'admin' ? '/admin' : '/judge')
  })
  if (auth?.kind !== 'staff') return <Navigate to="/staff" replace />
  const minimum = auth.role === 'admin' ? 8 : 4
  return (
    <AuthCard title="Choose your own password" subtitle={`Hi ${auth.name}. Replace the one an admin gave you.`}>
      <form onSubmit={onSubmit} className="stack">
        <label>
          Password or PIN you were given
          <input name="current_password" type="password" required autoComplete="current-password" />
        </label>
        <label>
          New password or PIN
          <input name="new_password" type="password" required minLength={minimum} autoComplete="new-password" />
        </label>
        <label>
          New password again
          <input name="confirm" type="password" required autoComplete="new-password" />
        </label>
        <p className="hint">At least {minimum} characters.</p>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit">
          <KeyRound size={18} />
          Save and continue
        </button>
      </form>
    </AuthCard>
  )
}

export function MyTeam() {
  const { auth, signOut } = useAuth()
  const token = auth?.kind === 'team' ? auth.token : null
  const { data, loading, error } = useApi<TeamPage>(token ? '/team/me' : null, token)
  if (!token) return <Navigate to="/login" replace />
  if (error?.status === 401 || error?.status === 403) {
    return (
      <>
        <p role="alert" className="error">Your login has expired.</p>
        <button type="button" onClick={signOut}>
          Log in again
        </button>
      </>
    )
  }
  return (
    <>
      {data ? <TeamDetails team={data} /> : <Status loading={loading} error={error} />}
      <button type="button" className="secondary" onClick={signOut}>
        <LogOut size={18} />
        Log out
      </button>
    </>
  )
}
