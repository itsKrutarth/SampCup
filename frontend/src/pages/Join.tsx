import { UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'

import Logo from '../components/Logo'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useApi } from '../lib/live'
import { isPhone, loginName } from '../lib/phone'

type Claimed = { token: string; player: { id: number; first_name: string } }

/** A registered player claims their account: name and email must match the registration (the center comes from it). */
export default function Join() {
  const { auth, signIn } = useAuth()
  const navigate = useNavigate()
  const status = useApi<{ open: boolean; loaded?: boolean }>('/registration/status')
  const [error, setError] = useState('')
  if (auth?.kind === 'player') return <Navigate to="/my-team" replace />
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const phone = String(form.get('phone') ?? '')
    if (!isPhone(phone)) {
      setError('Enter your 10-digit phone number')
      return
    }
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
          email: form.get('email'),
          username: loginName(phone), // the phone number is the username
          password: form.get('password'),
        },
      })
      signIn({ token: result.token, kind: 'player', name: result.player.first_name })
      navigate('/my-team')
    } catch (e) {
      const message = (e as ApiError).message
      setError(/username is taken/i.test(message) ? 'This phone number already has an account. Log in with it, or ask an admin.' : message)
    }
  }
  return (
    <section className="auth">
      <header>
        <Logo size={110} />
        <h1>Create your account</h1>
        <p className="muted">Use your name and the email you registered with on MySatsang.</p>
      </header>
      {status.data && !status.data.open && (
        <p role="alert" className="error">Team registration is closed. Ask an admin if you need a change.</p>
      )}
      {status.data?.loaded === false && <p className="info">Registrations have not been loaded yet. Check back soon.</p>}
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
          Registration email
          <input name="email" type="email" required maxLength={254} autoCapitalize="none" autoComplete="email" />
        </label>
        <label>
          Phone number
          <input name="phone" type="tel" inputMode="tel" required maxLength={20} autoComplete="tel" placeholder="508 555 1234" />
          <small className="hint">You log in with this number and your password.</small>
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
