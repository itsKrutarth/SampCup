import { KeyRound, LogIn, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'

import Logo from '../components/Logo'
import { api, ApiError } from '../lib/api'
import { useAuth, type Auth } from '../lib/auth'
import { loginName } from '../lib/phone'

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
        <Logo size={110} />
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

type PlayerUser = { first_name: string; must_change_password: boolean }

export function PlayerLogin() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const { error, onSubmit } = useSubmit(async (form) => {
    const result = await api<{ token: string; player: PlayerUser }>('/auth/player-login', {
      method: 'POST',
      body: { username: loginName(String(form.get('username') ?? '')), password: form.get('password') },
    }).catch((e: ApiError) => {
      throw e.status === 401 ? new ApiError(401, 'Phone number or password is wrong') : e
    })
    const { player } = result
    signIn({ token: result.token, kind: 'player', name: player.first_name, mustChange: player.must_change_password })
    navigate(player.must_change_password ? '/account/password' : '/my-team')
  })
  return (
    <AuthCard title="Player login" subtitle="Log in with your phone number and the password you created.">
      <form onSubmit={onSubmit} className="stack">
        <label>
          Phone number
          <input name="username" type="tel" inputMode="tel" required autoComplete="username" autoCapitalize="none" />
        </label>
        <label>
          Password
          <input name="password" type="password" required autoComplete="current-password" />
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit">
          <LogIn size={18} />
          Log in
        </button>
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
    const result = await api<{ user?: StaffUser; player?: PlayerUser }>('/auth/change-password', {
      method: 'POST',
      token: auth?.token,
      body: { current_password: form.get('current_password'), new_password: form.get('new_password') },
    })
    if (result.user) {
      signIn(staffAuth(auth!.token, result.user))
      navigate(result.user.role === 'admin' ? '/admin' : '/judge')
    } else {
      signIn({ ...auth!, mustChange: false })
      navigate('/my-team')
    }
  })
  if (!auth) return <Navigate to="/login" replace />
  const minimum = auth.kind === 'player' ? 6 : auth.role === 'admin' ? 8 : 4
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
