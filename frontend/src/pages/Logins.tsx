import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'

import Status from '../components/Status'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useApi } from '../lib/live'
import type { TeamPage } from '../lib/types'
import { TeamDetails } from './TeamPage'

type StaffUser = { display_name: string; role: 'admin' | 'judge'; court: number | null }

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
    <form onSubmit={onSubmit} className="stack narrow">
      <h1>Team login</h1>
      <label>
        Team name
        <input name="team_name" required autoComplete="username" />
      </label>
      <label>
        Password
        <input name="password" type="password" required autoComplete="current-password" />
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit">Log in</button>
    </form>
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
    signIn({ token: result.token, kind: 'staff', name: user.display_name, role: user.role, court: user.court })
    navigate(user.role === 'admin' ? '/admin' : '/judge')
  })
  return (
    <form onSubmit={onSubmit} className="stack narrow">
      <h1>Staff login</h1>
      <label>
        Username
        <input name="username" required autoComplete="username" autoCapitalize="none" />
      </label>
      <label>
        Password or PIN
        <input name="password" type="password" required autoComplete="current-password" />
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit">Log in</button>
    </form>
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
        Log out
      </button>
    </>
  )
}
