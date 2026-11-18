import { UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'

import Logo from '../components/Logo'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useApi } from '../lib/live'

type Claimed = { token: string; player: { id: number; first_name: string } }

/** A registered player claims their account: name and center must match the registration. */
export default function Join() {
  const { auth, signIn } = useAuth()
  const navigate = useNavigate()
  const status = useApi<{ open: boolean }>('/registration/status')
  const centers = useApi<string[]>('/registration/centers')
  const [error, setError] = useState('')
  if (auth?.kind === 'player') return <Navigate to="/my-team" replace />
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    if (form.get('password') !== form.get('confirm')) {
      setError('The two passwords do not match')
      return
    }
    try {
      const result = await api<Claimed>('/players/claim', {
        method: 'POST',
        body: {
          first_name: form.get('first_name'),
          last_name: form.get('last_name'),
          center: form.get('center'),
          username: form.get('username'),
          password: form.get('password'),
        },
      })
      signIn({ token: result.token, kind: 'player', name: result.player.first_name })
      navigate('/my-team')
    } catch (e) {
      setError((e as ApiError).message)
    }
  }
  return (
    <section className="auth">
      <header>
        <Logo size={56} />
        <h1>Create your account</h1>
        <p className="muted">Use the name you registered with on MySatsang.</p>
      </header>
      {status.data && !status.data.open && (
        <p role="alert" className="error">Team registration is closed. Ask an admin if you need a change.</p>
      )}
      {centers.data?.length === 0 && <p className="info">Registrations have not been loaded yet. Check back soon.</p>}
      <form onSubmit={submit} className="stack">
        <label>
          First name
          <input name="first_name" required autoComplete="given-name" />
        </label>
        <label>
          Last name
          <input name="last_name" required autoComplete="family-name" />
        </label>
        <label>
          Center
          <select name="center" required defaultValue="">
            <option value="" disabled>
              Choose your center…
            </option>
            {centers.data?.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Username
          <input name="username" required minLength={3} maxLength={30} autoCapitalize="none" autoComplete="username" />
        </label>
        <label>
          Password
          <input name="password" type="password" required minLength={6} autoComplete="new-password" />
        </label>
        <label>
          Password again
          <input name="confirm" type="password" required autoComplete="new-password" />
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit">
          <UserPlus size={18} />
          Create account
        </button>
        <p className="hint">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </section>
  )
}
