import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { api } from './api'
import { load, save } from './storage'

export type Auth = {
  token: string
  kind: 'team' | 'staff'
  name: string
  role?: 'admin' | 'judge'
  court?: number | null
}

type AuthState = {
  auth: Auth | null
  signIn: (auth: Auth) => void
  signOut: () => void
}

const KEY = 'sampcup-auth'
const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<Auth | null>(() => load<Auth | null>(KEY, null))
  const signIn = useCallback((next: Auth) => {
    save(KEY, next)
    setAuth(next)
  }, [])
  const signOut = useCallback(() => {
    setAuth((current) => {
      if (current) api('/auth/logout', { method: 'POST', token: current.token }).catch(() => {})
      return null
    })
    save(KEY, null)
  }, [])
  const value = useMemo(() => ({ auth, signIn, signOut }), [auth, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth needs <AuthProvider>')
  return state
}
